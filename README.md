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

**Guest VLAN Fallback:** Tanınmayan MAC adresleri veya yetkilendirme profili bulunmayan cihazlar otomatik olarak guest VLAN'a (varsayılan VLAN 30) yönlendirilir.

Ardışık başarısız girişler Redis üzerinden sayılır; `MAX_FAILED_ATTEMPTS` eşiği aşıldığında hesap `RATE_LIMIT_WINDOW` saniye süreyle bloke edilir. Redis erişilemez durumdaysa kimlik doğrulama engellenmez (graceful degradation).

## Kurulum

Docker ve Docker Compose kurulu olmalıdır.

```bash
cp .env.example .env
docker compose up -d --build
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

Sistem ayağa kalktığında `seed.py` aracılığıyla test verileri otomatik yüklenir (`SEED_ENABLED=true` olmalıdır).

### Unit Testler

```bash
docker compose exec api pytest test_models.py -v
```

19 test: `is_mac_address`, `build_vlan_response` ve IP validasyonu kapsar.

### PAP Doğrulama

```bash
docker compose exec freeradius radtest admin Password123! localhost 0 testing123
```

Beklenen: `Access-Accept` + VLAN 10 (`Tunnel-Private-Group-Id = 10`)

### MAB Doğrulama

```bash
echo 'User-Name="AA:BB:CC:DD:EE:FF", User-Password="AA:BB:CC:DD:EE:FF", Calling-Station-Id="AA:BB:CC:DD:EE:FF", NAS-IP-Address="127.0.0.1"' \
  | docker compose exec -T freeradius radclient localhost auth testing123
```

Beklenen: `Access-Accept` + VLAN 20

> **Not:** `User-Password` attribute'u gereklidir. FreeRADIUS authenticate aşamasına geçebilmesi için bu alanı bekler; MAB'da değeri MAC adresinin kendisidir.

### Guest VLAN Fallback

```bash
echo 'User-Name="11:22:33:44:55:66", User-Password="11:22:33:44:55:66", Calling-Station-Id="11:22:33:44:55:66", NAS-IP-Address="127.0.0.1"' \
  | docker compose exec -T freeradius radclient localhost auth testing123
```

Beklenen: `Access-Accept` + VLAN 30 (tanınmayan MAC → guest VLAN)

### Rate Limit

```bash
for i in {1..6}; do
  docker compose exec freeradius radtest ratelimituser WrongPass localhost 0 testing123
done
```

Beklenen: 6. denemede `Access-Reject` — `429 Too Many Requests`

### Accounting

```bash
# Start
echo 'Acct-Session-Id="TEST-123", User-Name="admin", Acct-Status-Type="Start", NAS-IP-Address="127.0.0.1"' \
  | docker compose exec -T freeradius radclient localhost acct testing123

# Interim-Update
echo 'Acct-Session-Id="TEST-123", User-Name="admin", Acct-Status-Type="Interim-Update", Acct-Input-Octets=1500, Acct-Output-Octets=2500, Acct-Session-Time=300, NAS-IP-Address="127.0.0.1"' \
  | docker compose exec -T freeradius radclient localhost acct testing123

# Stop
echo 'Acct-Session-Id="TEST-123", User-Name="admin", Acct-Status-Type="Stop", Acct-Session-Time=800, Acct-Input-Octets=2000, Acct-Output-Octets=5000, NAS-IP-Address="127.0.0.1"' \
  | docker compose exec -T freeradius radclient localhost acct testing123
```

Start sonrası `/sessions/active` üzerinde oturum görünür. Stop sonrası Redis'ten düşer, `/sessions/history` üzerinde nihai süreleriyle kayıtlı kalır.

### Orphan Accounting

Daha önce Start gönderilmemiş bir oturum için doğrudan Stop gönderildiğinde, sistem kaydı yine de oluşturur:

```bash
echo 'Acct-Session-Id="ORPHAN-999", User-Name="admin", Acct-Status-Type="Stop", Acct-Session-Time=120, NAS-IP-Address="127.0.0.1"' \
  | docker compose exec -T freeradius radclient localhost acct testing123
```

Beklenen: Accounting-Response + API loglarında `WARNING — Orphan accounting stop` kaydı.

## Logging ve Graceful Shutdown

Uygulama merkezi logging yapılandırması kullanır. Tüm modüller `nac.*` hiyerarşisinde loglar üretir:

```
2025-01-15 10:30:00 [INFO] nac: NAC Policy Engine başlatılıyor...
2025-01-15 10:30:01 [INFO] nac.auth: PAP doğrulama başarılı: admin
2025-01-15 10:30:02 [WARNING] nac.accounting: Orphan accounting stop: session=ORPHAN-999
```

`docker compose down` sırasında PostgreSQL bağlantı havuzu ve Redis bağlantısı düzgün şekilde kapatılır (graceful shutdown).

## Ortam Değişkenleri

`.env.example` dosyasını kopyalayarak düzenleyin:

```
DB_NAME=radius
DB_USER=radius
DB_PASSWORD=
REDIS_PASSWORD=
RADIUS_SECRET=
MAX_FAILED_ATTEMPTS=5
RATE_LIMIT_WINDOW=300
SEED_ENABLED=true
```

| Değişken | Açıklama | Varsayılan |
|---|---|---|
| `SEED_ENABLED` | Test verilerinin otomatik yüklenmesi | `true` |
| `MAX_FAILED_ATTEMPTS` | Rate limit tetikleme eşiği | `5` |
| `RATE_LIMIT_WINDOW` | Blokaj süresi (saniye) | `300` |
