# NAC Sistemi — FreeRADIUS + FastAPI

RADIUS protokolünü modern bir REST API arka ucu ile birleştiren modüler bir Network Access Control sistemi. FreeRADIUS üzerinden gelen kimlik doğrulama ve yetkilendirme kararları, `rlm_rest` entegrasyonu aracılığıyla FastAPI tabanlı bir Policy Engine'e yönlendirilir.

## Mimari

```
[Switch / AP / NAS]
        │  RADIUS (UDP 1812/1813)
        ▼
  [FreeRADIUS 3.2]
        │  rlm_rest (HTTP/JSON)
        ▼
  [FastAPI Policy Engine]
      │           │
      ▼           ▼
[PostgreSQL]   [Redis]
```

| Bileşen | Görev |
|---|---|
| FreeRADIUS | Access-Request ve Accounting paketlerini karşılar, kararı API'ye devreder |
| FastAPI | PAP ve MAB doğrulama, VLAN yetkilendirme, accounting kayıt motoru |
| PostgreSQL | Kullanıcılar, onaylı MAC adresleri, grup/VLAN profilleri, oturum geçmişi |
| Redis | Rate-limit sayaçları ve anlık aktif oturum önbelleği |

## Kimlik Doğrulama Akışı

**PAP:** Kullanıcı adı + şifre → bcrypt doğrulama → VLAN ataması

**MAB:** MAC adresi → `mac_devices` tablosu eşleştirmesi → VLAN ataması

Ardışık başarısız girişler Redis üzerinden sayılır; `MAX_FAILED_ATTEMPTS` eşiği aşıldığında hesap `RATE_LIMIT_WINDOW` saniye süreyle bloke edilir.

## Kurulum

Docker ve Docker Compose kurulu olmalıdır.

```bash
cp .env.example .env
docker-compose up -d --build
```

Sistem healthcheck döngülerini tamamladıktan sonra (~15 saniye) tüm servisler `healthy` duruma geçer.

API dokümantasyonu: `http://localhost:8000/docs`

## Endpoint'ler

| Endpoint | Metot | Açıklama |
|---|---|---|
| `/auth` | POST | PAP / MAB kimlik doğrulama |
| `/authorize` | POST | VLAN ve politika atribütleri |
| `/accounting` | POST | Oturum başlat / güncelle / bitir |
| `/users/` | GET | Kayıtlı kullanıcılar |
| `/users/mac` | GET | Kayıtlı MAC cihazlar |
| `/users/groups` | GET | Grup ve VLAN tanımları |
| `/sessions/active` | GET | Anlık aktif oturumlar (Redis) |
| `/sessions/history` | GET | Geçmiş oturumlar (PostgreSQL) |

## Test

Sistem ayağa kalktığında `seed.py` aracılığıyla test verileri otomatik yüklenir.

### PAP Doğrulama

```bash
docker exec -i nac-freeradius radtest admin Password123! localhost 0 testing123
```

Beklenen: `Access-Accept` + VLAN 10 (`Tunnel-Private-Group-Id = 10`)

### MAB Doğrulama

```bash
echo 'User-Name="AA:BB:CC:DD:EE:FF", Calling-Station-Id="AA:BB:CC:DD:EE:FF", NAS-IP-Address="127.0.0.1"' \
  | docker exec -i nac-freeradius radclient localhost auth testing123
```

Beklenen: `Access-Accept` + VLAN 20

### Rate Limit

```bash
for i in {1..6}; do
  docker exec -i nac-freeradius radtest ratelimituser WrongPass localhost 0 testing123
done
```

Beklenen: 6. denemede `Access-Reject` — `429 Too Many Requests`

### Accounting

```bash
# Start
echo 'Acct-Session-Id="TEST-123", User-Name="admin", Acct-Status-Type="Start", NAS-IP-Address="127.0.0.1"' \
  | docker exec -i nac-freeradius radclient localhost acct testing123

# Interim-Update
echo 'Acct-Session-Id="TEST-123", User-Name="admin", Acct-Status-Type="Interim-Update", Acct-Input-Octets=1500, Acct-Output-Octets=2500, Acct-Session-Time=300, NAS-IP-Address="127.0.0.1"' \
  | docker exec -i nac-freeradius radclient localhost acct testing123

# Stop
echo 'Acct-Session-Id="TEST-123", User-Name="admin", Acct-Status-Type="Stop", Acct-Session-Time=800, Acct-Input-Octets=2000, Acct-Output-Octets=5000, NAS-IP-Address="127.0.0.1"' \
  | docker exec -i nac-freeradius radclient localhost acct testing123
```

Start sonrası `/sessions/active` üzerinde oturum görünür. Stop sonrası Redis'ten düşer, `/sessions/history` üzerinde nihai süreleriyle kayıtlı kalır.

## Ortam Değişkenleri

`.env.example` dosyasını kopyalayarak düzenleyin:

```
DB_NAME=radius
DB_USER=radius
DB_PASSWORD=RadiusPass123!
REDIS_PASSWORD=RedisPass456!
RADIUS_SECRET=testing123
MAX_FAILED_ATTEMPTS=5
RATE_LIMIT_WINDOW=300
```