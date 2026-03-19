from fastapi import APIRouter
from typing import Optional
from redis_client import get_all_sessions
from database import get_db_pool

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.get("/active")
async def get_active_sessions():
    # Ağdaki online cihazların listesini Redis üzerinden anlık olarak getirir
    sessions = await get_all_sessions()
    return {
        "count": len(sessions),
        "sessions": sessions,
    }

@router.get("/history")
async def get_session_history(username: Optional[str] = None, limit: int = 50):
    # Geçmiş cihaz oturumlarını ve verilerini PostgreSQL (radacct) tablosundan filtreleyerek döner
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        if username:
            query = "SELECT * FROM radacct WHERE username = $1 ORDER BY radacctid DESC LIMIT $2"
            records = await conn.fetch(query, username, limit)
        else:
            query = "SELECT * FROM radacct ORDER BY radacctid DESC LIMIT $1"
            records = await conn.fetch(query, limit)
        
        # Tarihsel veriyi JSON formatına dönüştürülebilir hale getirmek için parse işlemi
        result = []
        for r in records:
            d = dict(r)
            for k, v in d.items():
                if hasattr(v, "isoformat"):
                    d[k] = v.isoformat()
            result.append(d)
        return result
