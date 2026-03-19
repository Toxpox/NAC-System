import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from passlib.context import CryptContext
from database import get_db_pool
from models import AuthRequest, AuthorizeRequest, AccountingRequest, is_mac_address, build_vlan_response
from redis_client import (
    get_failed_attempts, increment_failed_attempts, clear_failed_attempts,
    cache_session, update_session, remove_session, get_all_sessions
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama baslarken veritabani baglanti havuzunu olusturur
    await get_db_pool()
    yield


app = FastAPI(title="NAC Policy Engine", lifespan=lifespan)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
RATE_WINDOW  = int(os.getenv("RATE_LIMIT_WINDOW", "300"))

# --- 1. AUTHENTICATION ---
@app.post("/auth")
async def authenticate(req: AuthRequest):
    # MAC Authentication Bypass (MAB)
    if is_mac_address(req.username):
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            device = await conn.fetchrow(
                "SELECT mac_address, enabled FROM mac_devices WHERE mac_address = $1",
                req.username.upper()
            )
        if not device or not device["enabled"]:
            raise HTTPException(status_code=403, detail="Erisim Reddedildi")
        return {"status": "accept", "type": "mab"}

    # PAP Authentication & Brute-force Korumasi
    failed = await get_failed_attempts(req.username)
    if failed >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Cok fazla basarisiz deneme")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT username, password_hash, enabled FROM users WHERE username = $1",
            req.username
        )

    if not user or not user["enabled"]:
        await increment_failed_attempts(req.username, RATE_WINDOW)
        raise HTTPException(status_code=403, detail="Erisim Reddedildi")
        
    if not pwd_context.verify(req.password, user["password_hash"]):
        await increment_failed_attempts(req.username, RATE_WINDOW)
        raise HTTPException(status_code=403, detail="Hatali Sifre")
        
    await clear_failed_attempts(req.username)
    return {"status": "accept", "type": "pap"}


# --- 2. AUTHORIZATION ---
@app.post("/authorize")
async def authorize(req: AuthorizeRequest):
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        caller = req.calling_station_id or ""
        target = caller if is_mac_address(caller) else req.username
        
        if is_mac_address(target):
            row = await conn.fetchrow("""
                SELECT g.vlan_id FROM mac_devices m
                JOIN groups g ON m.group_name = g.group_name
                WHERE m.mac_address = $1 AND m.enabled = TRUE
            """, target.upper())
        else:
            row = await conn.fetchrow("""
                SELECT g.vlan_id FROM users u
                JOIN groups g ON u.group_name = g.group_name
                WHERE u.username = $1 AND u.enabled = TRUE
            """, target)

    if not row:
        raise HTTPException(status_code=403, detail="Yetkisiz Erisim")
        
    return build_vlan_response(row["vlan_id"])


# --- 3. ACCOUNTING ---
@app.post("/accounting")
async def accounting(req: AccountingRequest):
    pool = await get_db_pool()
    status = req.status_type.lower().replace("-", "_")
    
    stime = int(req.session_time or 0)
    ioctets = int(req.input_octets or 0)
    ooctets = int(req.output_octets or 0)

    async with pool.acquire() as conn:
        if status == "start":
            await conn.execute("""
                INSERT INTO radacct (acctsessionid, username, nasipaddress, acctstarttime, acctstatustype, callingstationid)
                VALUES ($1, $2, $3::inet, NOW(), 'Start', $4)
                ON CONFLICT DO NOTHING
            """, req.session_id, req.username, req.nas_ip or "0.0.0.0", req.calling_station_id or "")
            
            await cache_session(req.session_id, {
                "session_id":         req.session_id,
                "username":           req.username,
                "nas_ip":             req.nas_ip,
                "calling_station_id": req.calling_station_id,
                "status":             "active",
                "input_octets":       0,
                "output_octets":      0,
            })
            
        elif status == "interim_update":
            await conn.execute("""
                UPDATE radacct SET acctsessiontime = $2, acctinputoctets = $3, acctoutputoctets = $4, acctstatustype = 'Interim-Update'
                WHERE acctsessionid = $1
            """, req.session_id, stime, ioctets, ooctets)
            
            await update_session(req.session_id, {
                "session_time":  stime,
                "input_octets":  ioctets,
                "output_octets": ooctets,
            })
            
        elif status == "stop":
            await conn.execute("""
                UPDATE radacct SET acctstoptime = NOW(), acctsessiontime = $2, acctinputoctets = $3, acctoutputoctets = $4, acctstatustype = 'Stop'
                WHERE acctsessionid = $1
            """, req.session_id, stime, ioctets, ooctets)
            
            await remove_session(req.session_id)

    return {"status": "ok"}


# --- 4. SESSIONS API ---
@app.get("/sessions/active")
async def get_active_sessions():
    sessions = await get_all_sessions()
    return {
        "count": len(sessions),
        "sessions": sessions,
    }


# --- 5. EK YAPI/KONTROLLER ---
@app.post("/post-auth")
async def post_auth(req: dict):
    return {"status": "ok"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
