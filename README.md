# NAC Sistemi

Bu proje, RADIUS protokolünü kullanarak temel düzeyde çalışan bir Network Access Control (NAC) sistemi sunmaktadır.
Sistem kimlik doğrulama (Authentication), yetkilendirme (Authorization) ve hesap yönetimi (Accounting) işlemlerini yerine getirir. 

Docker Compose ile orkestre edilen altyapı bileşenleri:
- **FreeRADIUS:** RADIUS sunucusu (auth, authz, acct).
- **PostgreSQL:** Kullanıcı, cihaz (MAC) ve accounting (oturum) veritabanı.
- **Redis:** Oturum önbelleği ve rate-limit sayacı.
- **FastAPI (Python 3.13):** RADIUS isteklerini `rlm_rest` ile karşılayıp karara bağlayan "Policy Engine".

## Kurulum
Detaylı kurulum talimatları ve test komutları sonraki aşamalarda eklenecektir.
