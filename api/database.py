import os
from typing import Optional
import asyncpg

# Global veritabanı bağlantı havuzu
_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    global _pool
    # Havuz henüz oluşturulmadıysa veya kapalı bağlantılar varsa yeniden oluştur
    if _pool is None or _pool._closed:
        _pool = await asyncpg.create_pool(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "radius"),
            user=os.getenv("DB_USER", "radius"),
            password=os.getenv("DB_PASSWORD", "radius"),
            min_size=2,
            max_size=10,
        )
    return _pool


async def create_tables():
    # Güvenli veritabanı bağlantısını al
    pool = await get_db_pool()
    # Bağlantıyı bir kereye mahsus (context) aç ve sorguyu işlet
    async with pool.acquire() as conn:
        try:
            # Şu an 'public' şemasındaki tabloları getirip ekrana basıyor (varlığını teyit amaçlı)
            # Normal şartlarda INIT tarafında çalıştığı için burada doğrulama yapıyor
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            print(f"Veritabanı hazır, tablolar: {[r['tablename'] for r in tables]}")
        except Exception as e:
            print(f"Veritabanı tablolara erişirken veya oluştururken hata: {e}")