import json
import os
from typing import Optional
import redis.asyncio as aioredis

# Global redis bağlantı nesnesi (Singleton)
_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    # Bağlantıyı kontrol eder, yoksa environment (ortam değişkenleri) ile yeni bir bağlantı açar
    global _redis
    if _redis is None:
        _redis = aioredis.Redis(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True, # Dizi yerine direk string çevirisi yapılması için
        )
    return _redis


async def get_failed_attempts(username: str) -> int:
    # Kullanıcının Rate Limit (hız sınırı) kuralına takılıp takılmadığını bulmak için redis'teki sayacı getirir
    r = await get_redis()
    count = await r.get(f"rate_limit:{username}")
    return int(count) if count else 0


async def increment_failed_attempts(username: str, window: int) -> int:
    # Şifresini yanlış giren bir kullanıcının sayacını arttırır (pipeline sayesinde performanslı bir şekilde expiration'ı da atar)
    r = await get_redis()
    key = f"rate_limit:{username}"
    pipe = r.pipeline()
    pipe.incr(key)                  # Sayacı 1 arttırır
    pipe.expire(key, window)        # Belirli bir saniye (window) için sayacın geçerli olmasını sağlar
    results = await pipe.execute()
    return results[0]


async def clear_failed_attempts(username: str):
    # Başarılı (doğru) giriş durumunda başarısız giriş sayacını Redis üzerinden sıfırlar/siler
    r = await get_redis()
    await r.delete(f"rate_limit:{username}")


async def cache_session(session_id: str, data: dict):
    # Accounting-Start paketi geldiğinde kullanıcının oturumunu aktif oturum (active_sessions) seti içerisine alır
    r = await get_redis()
    pipe = r.pipeline()
    pipe.set(f"session:{session_id}", json.dumps(data), ex=86400) # Oturum detayını 24 saatliğine (ex=86400) kaydeder
    pipe.sadd("active_sessions", session_id)
    await pipe.execute()


async def update_session(session_id: str, updates: dict):
    # Interim-Update paketi (veri aktarım güncellemesi) geldiğinde oturumun sadece belirli metriklerini (octets, vb) günceller
    r = await get_redis()
    key = f"session:{session_id}"
    existing = await r.get(key)
    if existing:
        data = json.loads(existing)
        data.update(updates)
        await r.set(key, json.dumps(data), keepttl=True) # Süreyi (ttl) sıfırlamadan güncellemeyi işler


async def remove_session(session_id: str):
    # Accounting-Stop geldiğinde aktif oturumu listeden ve cache'ten çıkartır
    r = await get_redis()
    pipe = r.pipeline()
    pipe.delete(f"session:{session_id}")
    pipe.srem("active_sessions", session_id)
    await pipe.execute()


async def get_all_sessions() -> list:
    # Kurumda veya kampüste /sessions/active çağrıldığında o an aktif olan herkesin listesini Redis üzerinden performanslıca çeker
    r = await get_redis()
    ids = await r.smembers("active_sessions")
    sessions = []
    for sid in ids:
        raw = await r.get(f"session:{sid}")
        if raw:
            sessions.append(json.loads(raw))
    return sessions
