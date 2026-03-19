from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import create_tables
from seed import seed_data
from routers import auth, authorize, accounting, users, sessions


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Uygulama başlarken veritabanı tablolarını oluşturur
    await create_tables()
    # Gerekli örnek, test verilerini (admin kullanıcısı vb.) veritabanına ekler
    await seed_data()
    yield
    # Uygulama kapanırken eklenecek temizlik işlemleri buraya yazılabilir


# FastAPI ana uygulamasını başlatma (Ömür döngüsü ile birlikte)
app = FastAPI(title="NAC Policy Engine", lifespan=lifespan)

# Endpointlerin (Router'ların) uygulamaya dahil edilmesi
app.include_router(auth.router,       tags=["Authentication"])
app.include_router(authorize.router,  tags=["Authorization"])
app.include_router(accounting.router, tags=["Accounting"])
app.include_router(users.router,      tags=["Users"])
app.include_router(sessions.router,   tags=["Sessions"])


@app.get("/health")
async def health():
    # Docker Compose veya orchestrator'ların uygulamanın ayakta olup olmadığını kontrol edebilmesi için basit sağlık kontrolü
    return {"status": "healthy"}