from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import get_db_pool, create_tables
from seed import seed_data
from routers import auth, authorize, accounting, sessions, users

@asynccontextmanager
async def lifespan(app: FastAPI):
    # REST API başlatıldığında veritabanı bağlantı havuzunu ve seed(sahte veri) fonksiyonunu tetikler
    await get_db_pool()
    await create_tables()
    await seed_data()
    yield

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