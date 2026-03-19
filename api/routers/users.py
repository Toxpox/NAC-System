from fastapi import APIRouter, HTTPException
from database import get_db_pool
from passlib.context import CryptContext
import asyncpg
from models import UserCreate, MacDeviceCreate

router = APIRouter(prefix="/users", tags=["Users"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/")
async def get_all_users():
    # Sisteme kayıtlı PAP kullanıcılarını döner
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT id, username, group_name, enabled, created_at, last_login FROM users")
        return [dict(r) for r in records]

@router.post("/")
async def create_user(user: UserCreate):
    # Sisteme yeni kimlik doğrulama hesabı ekler
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        hashed_password = pwd_context.hash(user.password)
        try:
            await conn.execute(
                "INSERT INTO users (username, password_hash, group_name) VALUES ($1, $2, $3)",
                user.username, hashed_password, user.group_name
            )
            return {"status": "success", "message": "Kullanici eklendi"}
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Bu kullanici adi zaten mevcut")
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(status_code=400, detail="Gecersiz grup adi")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/mac")
async def list_mac_devices():
    # Sisteme kayıtlı olan cihaz (MAB) loglarını döner
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT id, mac_address, group_name, device_type, enabled FROM mac_devices")
        return [dict(r) for r in records]

@router.post("/mac")
async def add_mac_device(device: MacDeviceCreate):
    # Ağdaki switch ve portlara erişim hakkına sahip olacak MAC adresilerini sisteme kaydeder
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        try:
            await conn.execute(
                "INSERT INTO mac_devices (mac_address, group_name, device_type) VALUES ($1, $2, $3)",
                device.mac_address.upper(), device.group_name, device.device_type
            )
            return {"status": "success", "message": "Cihaz eklendi"}
        except asyncpg.UniqueViolationError:
            raise HTTPException(status_code=409, detail="Bu MAC adresi zaten kayitli")
        except asyncpg.ForeignKeyViolationError:
            raise HTTPException(status_code=400, detail="Gecersiz grup adi")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))


@router.get("/groups")
async def list_groups():
    # VLAN ve yetki ağlarını dönen metod
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        records = await conn.fetch("SELECT group_name, vlan_id, description FROM groups")
        return [dict(r) for r in records]