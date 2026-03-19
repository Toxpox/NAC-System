import os
from typing import Optional
import asyncpg

_pool: Optional[asyncpg.Pool] = None

async def get_db_pool() -> asyncpg.Pool:
    global _pool
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
    # Hizmet ilk ayaga kalktiginda tablolarin varligini garanti altina alan metod.
    # init.sql calismadigi veya bypass edildigi durumlarda (testing vb.) veritabani butunlugunu saglar.
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            group_name VARCHAR(50) PRIMARY KEY,
            vlan_id INTEGER NOT NULL,
            description TEXT
        );
        ''')
        
        await conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            username VARCHAR(100) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            group_name VARCHAR(50) REFERENCES groups(group_name),
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP WITH TIME ZONE
        );
        ''')

        await conn.execute('''
        CREATE TABLE IF NOT EXISTS mac_devices (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            mac_address VARCHAR(17) UNIQUE NOT NULL,
            group_name VARCHAR(50) REFERENCES groups(group_name),
            device_type VARCHAR(50),
            enabled BOOLEAN DEFAULT TRUE
        );
        ''')

        await conn.execute('''
        CREATE TABLE IF NOT EXISTS radacct (
            radacctid BIGSERIAL PRIMARY KEY,
            acctsessionid VARCHAR(64) NOT NULL UNIQUE,
            acctuniqueid VARCHAR(32),
            username VARCHAR(64) NOT NULL,
            groupname VARCHAR(64),
            realm VARCHAR(64),
            nasipaddress INET NOT NULL,
            nasportid VARCHAR(32),
            nasporttype VARCHAR(32),
            acctstarttime TIMESTAMP WITH TIME ZONE,
            acctupdatetime TIMESTAMP WITH TIME ZONE,
            acctstoptime TIMESTAMP WITH TIME ZONE,
            acctinterval INTEGER,
            acctsessiontime INTEGER,
            acctauthentic VARCHAR(32),
            connectinfo_start VARCHAR(128),
            connectinfo_stop VARCHAR(128),
            acctinputoctets BIGINT,
            acctoutputoctets BIGINT,
            calledstationid VARCHAR(50),
            callingstationid VARCHAR(50),
            acctterminatecause VARCHAR(32),
            servicetype VARCHAR(32),
            framedprotocol VARCHAR(32),
            framedipaddress INET,
            acctstatustype VARCHAR(32)
        );
        ''')

        await conn.execute('''
        INSERT INTO groups (group_name, vlan_id, description) VALUES
        ('admin', 10, 'Yonetim ve Altyapi VLAN'),
        ('employee', 20, 'Standart Personel VLAN'),
        ('guest', 30, 'Misafir ve Izole Edilmis VLAN')
        ON CONFLICT DO NOTHING;
        ''')