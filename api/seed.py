import os
import logging
from passlib.context import CryptContext
from database import get_db_pool

logger = logging.getLogger("nac.seed")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


async def seed_data():
    # Uygulama başlangıcında otomatik oluşturulacak deneme kayıtları (Seed)
    # Üretim ortamında SEED_ENABLED=false ile devre dışı bırakılabilir
    if os.getenv("SEED_ENABLED", "true").lower() != "true":
        logger.info("Seed devre dışı (SEED_ENABLED != true)")
        return
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        
        # Standart şifremiz Password123!
        admin_pass = pwd_context.hash("Password123!")
        emp_pass   = pwd_context.hash("EmployeePass!")

        # 1. PAP hesaplarının yaratılması
        # ON CONFLICT DO NOTHING: Aynı kullanıcı adı veya id mevcutsa işlemi atlar 
        await conn.execute("""
            INSERT INTO users (username, password_hash, group_name)
            VALUES 
                ('admin', $1, 'admin'),
                ('employee1', $2, 'employee')
            ON CONFLICT (username) DO NOTHING
        """, admin_pass, emp_pass)

        # Rate Limit testi amacıyla kullanılan dummy PAP hesabı
        await conn.execute("""
            INSERT INTO users (username, password_hash, group_name)
            VALUES 
                ('ratelimituser', $1, 'employee')
            ON CONFLICT (username) DO NOTHING
        """, emp_pass)

        # 2. MAB (MAC Bypass) hesaplarının varoluşu
        await conn.execute("""
            INSERT INTO mac_devices (mac_address, group_name, device_type)
            VALUES 
                ('AA:BB:CC:DD:EE:FF', 'employee', 'IP Phone'),
                ('11:22:33:44:55:66', 'guest', 'Guest Laptop')
            ON CONFLICT (mac_address) DO NOTHING
        """)

        logger.info("Örnek veriler içeri eklendi veya zaten mevcut.")