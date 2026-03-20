import logging
import asyncpg
from fastapi import APIRouter, HTTPException
from database import get_db_pool
from models import AccountingRequest
from redis_client import cache_session, update_session, remove_session

logger = logging.getLogger("nac.accounting")

router = APIRouter()

@router.post("/accounting")
async def accounting(req: AccountingRequest):
    # FreeRADIUS ağ muhasebesi (Start, Interim, Stop) paketlerini işler
    try:
        pool = await get_db_pool()
    except asyncpg.PostgresError as e:
        logger.error(f"Accounting veritabanı bağlantı hatası: {e}")
        raise HTTPException(status_code=503, detail="Veritabanı erişilemiyor")

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
        else:
            logger.warning(f"Bilinmeyen accounting status tipi: {req.status_type}")

    return {"status": "ok"}


async def _handle_start(conn, req: AccountingRequest):
    # Yeni cihazın sisteme dahil olması
    await conn.execute("""
        INSERT INTO radacct (acctsessionid, username, nasipaddress, acctstarttime, acctstatustype, callingstationid)
        VALUES ($1, $2, $3::inet, NOW(), 'Start', $4)
        ON CONFLICT DO NOTHING
    """, req.session_id, req.username, req.nas_ip or "0.0.0.0", req.calling_station_id or "")

    logger.info(f"Accounting Start: session={req.session_id}, user={req.username}")

    # Redis cache — erişilemezse accounting kaybedilmez, sadece aktif oturum listesi eksik kalır
    try:
        await cache_session(req.session_id, {
            "session_id": req.session_id,
            "username": req.username,
            "nas_ip": req.nas_ip,
            "calling_station_id": req.calling_station_id,
            "status": "active",
            "input_octets": 0,
            "output_octets": 0,
        })
    except Exception as e:
        logger.warning(f"Redis cache başarısız (start): {e}")


async def _handle_interim_update(conn, req: AccountingRequest, stime: int, ioctets: int, ooctets: int):
    # Kotada anlık güncellemeler ve kullanım bilgisi
    await conn.execute("""
        UPDATE radacct SET acctsessiontime = $2, acctinputoctets = $3, acctoutputoctets = $4,
               acctstatustype = 'Interim-Update', acctupdatetime = NOW()
        WHERE acctsessionid = $1
    """, req.session_id, stime, ioctets, ooctets)

    try:
        await update_session(req.session_id, {
            "session_time": stime,
            "input_octets": ioctets,
            "output_octets": ooctets,
        })
    except Exception as e:
        logger.warning(f"Redis cache başarısız (interim): {e}")


async def _handle_stop(conn, req: AccountingRequest, stime: int, ioctets: int, ooctets: int):
    # Ağ cihazından ayrılan veya çıkarılan kullanıcıların oturumlarını kapatma
    result = await conn.execute("""
        UPDATE radacct SET acctstoptime = NOW(), acctsessiontime = $2, acctinputoctets = $3,
               acctoutputoctets = $4, acctstatustype = 'Stop', acctterminatecause = $5
        WHERE acctsessionid = $1
    """, req.session_id, stime, ioctets, ooctets, req.terminate_cause or "")

    # Orphan stop: Start paketi hiç gelmemiş olabilir (ağda paket kaybı)
    if result == "UPDATE 0":
        logger.warning(f"Orphan accounting stop: session={req.session_id} — Start paketi alınmamış, kayıt oluşturuluyor")
        await conn.execute("""
            INSERT INTO radacct (acctsessionid, username, nasipaddress, acctstarttime, acctstoptime,
                                 acctsessiontime, acctinputoctets, acctoutputoctets, acctstatustype,
                                 acctterminatecause, callingstationid)
            VALUES ($1, $2, $3::inet, NOW(), NOW(), $4, $5, $6, 'Stop', $7, $8)
            ON CONFLICT DO NOTHING
        """, req.session_id, req.username, req.nas_ip or "0.0.0.0",
            stime, ioctets, ooctets, req.terminate_cause or "", req.calling_station_id or "")

    logger.info(f"Accounting Stop: session={req.session_id}, user={req.username}")

    try:
        await remove_session(req.session_id)
    except Exception as e:
        logger.warning(f"Redis cache başarısız (stop): {e}")