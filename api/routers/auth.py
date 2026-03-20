import os
import logging
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
import asyncpg
from database import get_db_pool
from models import AuthRequest, is_mac_address
from redis_client import get_failed_attempts, increment_failed_attempts, clear_failed_attempts

logger = logging.getLogger("nac.auth")

router = APIRouter()
# Şifreleri çözümlenemez bir hash formatında (bcrypt) doğrulayan kütüphanenin tanımlanması
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

MAX_ATTEMPTS = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
RATE_WINDOW  = int(os.getenv("RATE_LIMIT_WINDOW", "300"))


@router.post("/auth")
async def authenticate(req: AuthRequest):
    # FreeRADIUS Kullanıcı kimlik doğrulama Endpoint'i
    # Şirket / Kampüs ağına bağlanmak isteyen cihazın bilgilerine göre doğrulama türü (PAP / MAB) ayrımı yapılır
    if is_mac_address(req.username):
        return await _authenticate_mac(req.username)
    return await _authenticate_user(req.username, req.password)


async def _authenticate_mac(mac: str) -> dict:
    # MAC Authentication Bypass (MAB) Doğrulama Metodu
    # Kullanıcı adı veya şifre sağlamadan doğrudan ethernet üzerinden kimlik doğrulayan IP telefon vb. cihazlar için çalışır.
    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            device = await conn.fetchrow(
                "SELECT mac_address, group_name, enabled FROM mac_devices WHERE mac_address = $1",
                mac.upper()
            )
    except asyncpg.PostgresError as e:
        logger.error(f"MAB veritabanı hatası: {e}")
        raise HTTPException(status_code=503, detail="Veritabanı erişilemiyor")

    # Bilinmeyen MAC → guest VLAN'a yönlendir (reject yerine izole erişim sağla)
    if not device:
        logger.info(f"Bilinmeyen MAC guest VLAN'a yönlendiriliyor: {mac}")
        return {"status": "accept", "type": "mab", "group": "guest", "fallback": True}
    # Cihaz kayıtlı ama yöneticiler tarafından devre dışı (disabled) bırakılmışsa engeller
    if not device["enabled"]:
        logger.warning(f"Devre dışı MAC erişim denemesi: {mac}")
        raise HTTPException(status_code=403, detail="Devre dışı MAC")

    return {"status": "accept", "type": "mab"}


async def _authenticate_user(username: str, password: str) -> dict:
    # PAP Doğrulama Metodu
    # Redis rate-limit kontrolü — Redis erişilemezse auth çalışmaya devam eder (graceful degradation)
    try:
        failed = await get_failed_attempts(username)
        if failed >= MAX_ATTEMPTS:
            logger.warning(f"Rate limit aşıldı: {username}, {failed} deneme")
            raise HTTPException(status_code=429, detail="Çok fazla başarısız deneme")
    except HTTPException:
        raise
    except Exception as e:
        # Redis yoksa rate-limit devre dışı kalır ama auth çalışmaya devam eder
        logger.warning(f"Redis erişilemez, rate-limit atlanıyor: {e}")

    try:
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            user = await conn.fetchrow(
                "SELECT username, password_hash, enabled FROM users WHERE username = $1",
                username
            )
    except asyncpg.PostgresError as e:
        logger.error(f"PAP veritabanı hatası: {e}")
        raise HTTPException(status_code=503, detail="Veritabanı erişilemiyor")

    # Veritabanında eşleşen kullanıcı mevcut değilse başarısız limiti Redis üzerinden arttır ve Erişim reddet
    if not user:
        await _safe_increment(username)
        raise HTTPException(status_code=403, detail="Kullanıcı bulunamadı")

    # Kullanıcı hesabı kilitlenmiş/devre dışıysa kontrol et
    if not user["enabled"]:
        raise HTTPException(status_code=403, detail="Hesap devre dışı")

    # Bcrypt ile plaintext gönderilen parolayı, veritabanındaki hash ile kriptografik olarak kıyasla
    if not pwd_context.verify(password, user["password_hash"]):
        await _safe_increment(username)
        raise HTTPException(status_code=403, detail="Hatalı şifre")

    # Mükemmel eşleşme: Şifre doğru. Redis üzerindeki başarısız deneme sayısını sıfırla ve oturuma (Accept) izin ver
    await _safe_clear(username)
    logger.info(f"PAP doğrulama başarılı: {username}")
    return {"status": "accept", "type": "pap"}


async def _safe_increment(username: str):
    """Redis'e ulaşılamazsa sessizce devam et — rate-limit kaybı kabul edilebilir."""
    try:
        await increment_failed_attempts(username, RATE_WINDOW)
    except Exception as e:
        logger.warning(f"Redis rate-limit güncellenemedi: {e}")


async def _safe_clear(username: str):
    """Redis'e ulaşılamazsa sessizce devam et."""
    try:
        await clear_failed_attempts(username)
    except Exception as e:
        logger.warning(f"Redis rate-limit sıfırlanamadı: {e}")


@router.post("/post-auth")
async def post_auth(data: dict):
    # Erişim denemelerinden sonra FreeRADIUS tarafından bilgilendirme (loglama ve ekstra policy) amaçlı dönülen Post-Auth (Bitti) çağrısına cevap verir.
    return {"status": "ok"}