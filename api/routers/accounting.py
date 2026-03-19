from fastapi import APIRouter
from database import get_db_pool
from models import AccountingRequest
from redis_client import cache_session, update_session, remove_session

router = APIRouter()

@router.post("/accounting")
async def accounting(req: AccountingRequest):
    # FreeRADIUS ağ muhasebesi (Start, Interim, Stop) paketlerini işler
    pool = await get_db_pool()
    status = req.status_type.lower().replace("-", "_")
    
    stime = int(req.session_time or 0)
    ioctets = int(req.input_octets or 0)
    ooctets = int(req.output_octets or 0)

    async with pool.acquire() as conn:
        if status == "start":
            await _handle_start(conn, req)
        elif status == "interim_update":
            await _handle_interim_update(conn, req, stime, ioctets, ooctets)
        elif status == "stop":
            await _handle_stop(conn, req, stime, ioctets, ooctets)

    return {"status": "ok"}


async def _handle_start(conn, req: AccountingRequest):
    # Yeni cihazın sisteme dahil olması
    await conn.execute("""
        INSERT INTO radacct (acctsessionid, username, nasipaddress, acctstarttime, acctstatustype, callingstationid)
        VALUES ($1, $2, $3::inet, NOW(), 'Start', $4)
        ON CONFLICT DO NOTHING
    """, req.session_id, req.username, req.nas_ip or "0.0.0.0", req.calling_station_id or "")
    
    await cache_session(req.session_id, {
        "session_id": req.session_id,
        "username": req.username,
        "nas_ip": req.nas_ip,
        "calling_station_id": req.calling_station_id,
        "status": "active",
        "input_octets": 0,
        "output_octets": 0,
    })


async def _handle_interim_update(conn, req: AccountingRequest, stime: int, ioctets: int, ooctets: int):
    # Kotada anlık güncellemeler ve kullanım bilgisi
    await conn.execute("""
        UPDATE radacct SET acctsessiontime = $2, acctinputoctets = $3, acctoutputoctets = $4, acctstatustype = 'Interim-Update'
        WHERE acctsessionid = $1
    """, req.session_id, stime, ioctets, ooctets)
    
    await update_session(req.session_id, {
        "session_time": stime,
        "input_octets": ioctets,
        "output_octets": ooctets,
    })


async def _handle_stop(conn, req: AccountingRequest, stime: int, ioctets: int, ooctets: int):
    # Ağ cihazından ayrılan veya çıkarılan kullanıcıların oturumlarını kapatma
    await conn.execute("""
        UPDATE radacct SET acctstoptime = NOW(), acctsessiontime = $2, acctinputoctets = $3, acctoutputoctets = $4, acctstatustype = 'Stop'
        WHERE acctsessionid = $1
    """, req.session_id, stime, ioctets, ooctets)
    
    await remove_session(req.session_id)