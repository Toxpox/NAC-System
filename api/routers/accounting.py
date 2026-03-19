from fastapi import APIRouter
from database import get_db_pool
from models import AccountingRequest
from redis_client import cache_session, update_session, remove_session

router = APIRouter()


@router.post("/accounting")
async def accounting(req: AccountingRequest):
    # FreeRADIUS tarafından oturum bilgilerini tutmak için gönderilen Accounting paketlerini dinler
    status = req.status_type.lower().replace("-", "_")

    if status == "start":
        return await _handle_start(req)
    elif status == "interim_update":
        return await _handle_interim_update(req)
    elif status == "stop":
        return await _handle_stop(req)

    return {"status": "ok"}


async def _handle_start(req: AccountingRequest) -> dict:
    # Oturum başladığı anda çalışır. 
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # PostgreSQL tablomuz olan radacct içerisine oturum başlama kaydını atar.
        await conn.execute("""
            INSERT INTO radacct (
                acctsessionid, username, nasipaddress,
                acctstarttime, acctstatustype, callingstationid
            ) VALUES ($1, $2, $3::inet, NOW(), 'Start', $4)
            ON CONFLICT DO NOTHING
        """, req.session_id, req.username, req.nas_ip or "0.0.0.0",
            req.calling_station_id or "")

    # Hızlı erişim için oturum kaydını veritabanına ek olarak Redis belleğine yazar
    await cache_session(req.session_id, {
        "session_id":         req.session_id,
        "username":           req.username,
        "nas_ip":             req.nas_ip,
        "calling_station_id": req.calling_station_id,
        "status":             "active",
        "input_octets":       0,
        "output_octets":      0,
    })
    return {"status": "ok"}


async def _handle_interim_update(req: AccountingRequest) -> dict:
    # Kullanıcı bağlı kaldığı sürece düzenli aralıklarla gelen kullanım (Update) verisidir
    pool = await get_db_pool()
    
    # Payload içerisindeki kullanım verilerini güvenli int dönüşümüne tabi tutuyoruz
    stime = int(req.session_time or 0)
    ioctets = int(req.input_octets or 0)
    ooctets = int(req.output_octets or 0)
    
    async with pool.acquire() as conn:
        # Veritabanında oturumu bularak yeni kullanım bant genişliğini / süresini kaydeder
        await conn.execute("""
            UPDATE radacct
            SET acctsessiontime  = $2,
                acctinputoctets  = $3,
                acctoutputoctets = $4,
                acctstatustype   = 'Interim-Update'
            WHERE acctsessionid = $1
        """, req.session_id, stime, ioctets, ooctets)

    # Redis belleğinde sadece kullanım verilerini (delta) güncellersek performans artışı sağlarız
    await update_session(req.session_id, {
        "session_time":  stime,
        "input_octets":  ioctets,
        "output_octets": ooctets,
    })
    return {"status": "ok"}


async def _handle_stop(req: AccountingRequest) -> dict:
    # Kullanıcı bağlantıyı kopardığında, veya NAS timeout verdiğinde "Stop" paketi gelir.
    pool = await get_db_pool()
    stime = int(req.session_time or 0)
    ioctets = int(req.input_octets or 0)
    ooctets = int(req.output_octets or 0)
    
    async with pool.acquire() as conn:
        # Oturumun sonlandığı bitiş tarihini (NOW()) sisteme kaydeder
        await conn.execute("""
            UPDATE radacct
            SET acctstoptime     = NOW(),
                acctsessiontime  = $2,
                acctinputoctets  = $3,
                acctoutputoctets = $4,
                acctstatustype   = 'Stop'
            WHERE acctsessionid = $1
        """, req.session_id, stime, ioctets, ooctets)

    # Oturum bittiği için geçici (cache) veritabanımızdan bu oturum listesini silebiliriz.
    await remove_session(req.session_id)
    return {"status": "ok"}