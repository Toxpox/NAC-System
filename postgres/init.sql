-- PostgreSQL Schema Initialization

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Gruplar ve VLAN Atamaları
CREATE TABLE groups (
    group_name VARCHAR(50) PRIMARY KEY,
    vlan_id INTEGER NOT NULL,
    description TEXT
);

-- PAP Kimlik Doğrulaması İçin Personel/Admin Kullanıcıları
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    group_name VARCHAR(50) REFERENCES groups(group_name),
    enabled BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- MAB (MAC Authentication Bypass)
CREATE TABLE mac_devices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    mac_address VARCHAR(17) UNIQUE NOT NULL,
    group_name VARCHAR(50) REFERENCES groups(group_name),
    device_type VARCHAR(50),
    enabled BOOLEAN DEFAULT TRUE
);

-- Accounting
CREATE TABLE radacct (
    radacctid BIGSERIAL PRIMARY KEY,
    acctsessionid VARCHAR(64) NOT NULL,
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

CREATE UNIQUE INDEX idx_radacct_session ON radacct(acctsessionid);

-- Başlangıç verileri
INSERT INTO groups (group_name, vlan_id, description) VALUES
('admin', 10, 'Yonetim ve Altyapi VLAN'),
('employee', 20, 'Standart Personel VLAN'),
('guest', 30, 'Misafir ve Izole Edilmis VLAN')
ON CONFLICT DO NOTHING;
