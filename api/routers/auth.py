import os
from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from database import get_db_pool
from models import AuthRequest, is_mac_address
from redis_client import get_failed_attempts, increment_failed_attempts, clear_failed_attempts

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
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        device = await conn.fetchrow(
            "SELECT mac_address, enabled FROM mac_devices WHERE mac_address = $1",
            mac.upper()
        )
    
    # MAC adresi tabloda (veritabanında) eşleşmezse 403 (Reject - Erişim Reddedildi) döndürür
    if not device:
        raise HTTPException(status_code=403, detail="Bilinmeyen MAC")
    # Cihaz kayıtlı ama yöneticiler tarafından devre dışı (disabled) bırakılmışsa engeller
    if not device["enabled"]:
        raise HTTPException(status_code=403, detail="Devre dışı MAC")
    
    return {"status": "accept", "type": "mab"}


async def _authenticate_user(username: str, password: str) -> dict:
    # PAP Doğrulama Metodu
    # Kullanıcı adı veritabanında limit sınırlarını zorlamışsa, rate_limit sorgusu ile kullanıcıyı bloke eder
    failed = await get_failed_attempts(username)
    if failed >= MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Çok fazla başarısız deneme")

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        user = await conn.fetchrow(
            "SELECT username, password_hash, enabled FROM users WHERE username = $1",
            username
        )

    # Veritabanında eşleşen kullanıcı mevcut değilse başarısız limiti Redis üzerinden arttır ve Erişim reddet
    if not user:
        await increment_failed_attempts(username, RATE_WINDOW)
        raise HTTPException(status_code=403, detail="Kullanıcı bulunamadı")

    # Kullanıcı hesabı kilitlenmiş/devre dışıysa kontrol et
    if not user["enabled"]:
        raise HTTPException(status_code=403, detail="Hesap devre dışı")

    # Bcrypt ile plaintext gönderilen parolayı, veritabanındaki hash ile kriptografik olarak kıyasla
    if not pwd_context.verify(password, user["password_hash"]):
        await increment_failed_attempts(username, RATE_WINDOW)
        raise HTTPException(status_code=403, detail="Hatalı şifre")

    # Mükemmel eşleşme: Şifre doğru. Redis üzerindeki başarısız deneme sayısını sıfırla ve oturuma (Accept) izin ver
    await clear_failed_attempts(username)
    return {"status": "accept", "type": "pap"}


@router.post("/post-auth")
async def post_auth(data: dict):
    # Erişim denemelerinden sonra FreeRADIUS tarafından bilgilendirme (loglama ve ekstra policy) amaçlı dönülen Post-Auth (Bitti) çağrısına cevap verir.
    return {"status": "ok"}