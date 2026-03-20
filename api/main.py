import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import get_db_pool, create_tables, close_db_pool
from redis_client import close_redis
from seed import seed_data
from routers import auth, authorize, accounting, sessions, users

# Merkezi loglama yapılandırması — tüm modüller "nac" logger hiyerarşisini kullanır
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("nac")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: veritabanı bağlantı havuzu, tablo oluşturma ve seed veriler
    logger.info("NAC Policy Engine başlatılıyor...")
    await get_db_pool()
    await create_tables()
    await seed_data()
    logger.info("NAC Policy Engine hazır.")
    yield
    # Shutdown: açık bağlantıları düzgünce kapat
    logger.info("NAC Policy Engine kapatılıyor...")
    await close_db_pool()
    await close_redis()
    logger.info("Tüm bağlantılar kapatıldı.")

app = FastAPI(title="NAC Policy Engine", lifespan=lifespan)

# Yazılan modüler endpointlerin FastAPI'ye entegre edilmesi
app.include_router(auth.router)
app.include_router(authorize.router)
app.include_router(accounting.router)
app.include_router(sessions.router)
app.include_router(users.router)

@app.get("/health")
async def health():
    # Docker Healtcheck mekanizması için sağlık durumu dönüşü
    return {"status": "healthy"}