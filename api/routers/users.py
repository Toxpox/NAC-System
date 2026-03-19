from fastapi import APIRouter, HTTPException
from passlib.context import CryptContext
from database import get_db_pool
from models import UserCreate, MacDeviceCreate

router = APIRouter()
# Kayıt işlemlerinde (Kullanıcı oluşturma) alınacak şifrelerin plain-text kalmaması için CryptContext kullanımı
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.get("/users")
async def list_users():
    # Sistemdeki tüm PAP hesaplarını ve yetkilerini geri listeler
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT u.id, u.username, u.group_name, u.enabled,
                   u.created_at, u.last_login, g.vlan_id
            FROM users u
            JOIN groups g ON u.group_name = g.group_name
            ORDER BY u.username
        """)
    return [dict(r) for r in rows]


@router.post("/users", status_code=201)
async def create_user(req: UserCreate):
    # Yeni bir şirket çalışanı / konuk için hesap oluşturulması
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Girilen kullanıcının atanacağı grubun sistemde mevcut olup olmadığını dogrula (Yabancı Anahtar kontrolü)
        group = await conn.fetchrow(
            "SELECT group_name FROM groups WHERE group_name = $1",
            req.group_name
        )
        if not group:
            raise HTTPException(status_code=400, detail=f"Geçersiz grup: {req.group_name}")

        # Şifre ASLA plaintext kaydedilemez, Bcrypt ile formatlanmalıdır
        password_hash = pwd_context.hash(req.password)
        try:
            row = await conn.fetchrow("""
                INSERT INTO users (username, password_hash, group_name)
                VALUES ($1, $2, $3)
                RETURNING id, username, group_name, enabled, created_at
            """, req.username, password_hash, req.group_name)
        except Exception as e:
            # Veritabanında aynı isimde kullanıcı var mı? (UNIQUE hatası kontrolü)
            if "unique" in str(e).lower():
                raise HTTPException(status_code=409, detail="Kullanıcı zaten mevcut")
            raise HTTPException(status_code=500, detail=str(e))

    return dict(row)


@router.get("/mac-devices")
async def list_mac_devices():
    # Kurumdaki (Örneğin Yazıcı, IoT, Akıllı Cihazlar) tüm MAC adresli makineleri listeler
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT m.id, m.mac_address, m.group_name,
                   m.device_type, m.enabled, g.vlan_id
            FROM mac_devices m
            JOIN groups g ON m.group_name = g.group_name
            ORDER BY m.mac_address
        """)
    return [dict(r) for r in rows]


@router.post("/mac-devices", status_code=201)
async def add_mac_device(req: MacDeviceCreate):
    # Ağdaki onaylı cihazları bir gruba bağlayıp listeye ekler (MAB)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        group = await conn.fetchrow(
            "SELECT group_name FROM groups WHERE group_name = $1",
            req.group_name
        )
        if not group:
            raise HTTPException(status_code=400, detail=f"Geçersiz grup: {req.group_name}")

        try:
            row = await conn.fetchrow("""
                INSERT INTO mac_devices (mac_address, group_name, device_type)
                VALUES ($1, $2, $3)
                RETURNING id, mac_address, group_name, device_type, enabled
            """, req.mac_address, req.group_name, req.device_type)
        except Exception as e:
            if "unique" in str(e).lower():
                raise HTTPException(status_code=409, detail="MAC zaten kayıtlı")
            raise HTTPException(status_code=500, detail=str(e))

    return dict(row)


@router.get("/groups")
async def list_groups():
    # Ağ VLAN altyapısındaki grupları listeler (admin, employee, guest)
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT group_name, vlan_id, description FROM groups ORDER BY vlan_id"
        )
    return [dict(r) for r in rows]