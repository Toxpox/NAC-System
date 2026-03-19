from fastapi import APIRouter, Query
from database import get_db_pool
from redis_client import get_all_sessions

router = APIRouter()


@router.get("/sessions/active")
async def get_active_sessions():
    # PostgreSQL'i meşgul etmeden, yüksek hızlı Redis üzerinden bütün canlı cihaz listesini dönen endpoint
    sessions = await get_all_sessions()
    return {
        "count":    len(sessions),
        "sessions": sessions,
    }


@router.get("/sessions/history")
async def get_session_history(
    username: str | None = Query(None),
    limit:    int        = Query(50, ge=1, le=500), # Pagination (Limit) için varsayılan en fazla 500 döner
    offset:   int        = Query(0, ge=0),          # Başlangıç kaydı (Offset)
):
    # Geçmişe dönük oturum (History) sorgularını veritabanından listeler
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if username:
            # Sadece belirli bir kullanıcının geçmişini (loglarını) filtrelemek istersek
            rows = await conn.fetch("""
                SELECT radacctid, acctsessionid, username,
                       nasipaddress::text, acctstarttime, acctstoptime,
                       acctsessiontime, acctinputoctets, acctoutputoctets,
                       callingstationid, acctstatustype
                FROM radacct
                WHERE username = $1
                ORDER BY acctstarttime DESC
                LIMIT $2 OFFSET $3
            """, username, limit, offset)
        else:
            # Tüm sistem geçmişini görmek istersek (Dashboard vs.)
            rows = await conn.fetch("""
                SELECT radacctid, acctsessionid, username,
                       nasipaddress::text, acctstarttime, acctstoptime,
                       acctsessiontime, acctinputoctets, acctoutputoctets,
                       callingstationid, acctstatustype
                FROM radacct
                ORDER BY acctstarttime DESC
                LIMIT $1 OFFSET $2
            """, limit, offset)

    return {
        "count":    len(rows),
        "sessions": [dict(r) for r in rows],
    }
