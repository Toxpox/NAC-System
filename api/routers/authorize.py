from fastapi import APIRouter, HTTPException
from database import get_db_pool
from models import AuthorizeRequest, is_mac_address, build_vlan_response

router = APIRouter()


@router.post("/authorize")
async def authorize(req: AuthorizeRequest):
    # Cihaza/Kullanıcıya uygulanacak politika ve VLAN ataması için Authorize (Yetkilendirme) çağrısı
    caller = req.calling_station_id or ""
    # Gelen isteğin bir MAC cihazı bypass isteği olup olmadığını kontrol et
    if is_mac_address(caller) or is_mac_address(req.username):
        mac = caller if is_mac_address(caller) else req.username
        return await _authorize_mac(mac.upper())
    # MAC değilse, normal personelin veya yöneticinin grubunu kontrol et
    return await _authorize_user(req.username)


async def _authorize_user(username: str) -> dict:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # Kullanıcıların ait oldukları gruba (groups tablosu) göre VLAN ID değerini getir
        row = await conn.fetchrow("""
            SELECT u.group_name, g.vlan_id
            FROM users u
            JOIN groups g ON u.group_name = g.group_name
            WHERE u.username = $1 AND u.enabled = TRUE
        """, username)

    # Kullanıcı veritabanında yoksa veya yetkisizse Reddet
    if not row:
        raise HTTPException(status_code=403, detail="Kullanıcı bulunamadı veya yetkisiz")

    # Başarılı olan kullanıcılar için FreeRADIUS'a Tunnel-Type, VLAN gibi değerleri dön
    return build_vlan_response(row["vlan_id"])


async def _authorize_mac(mac: str) -> dict:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # MAC temelli cihazların ait olduğu grubu VLAN ataması için sorgula
        row = await conn.fetchrow("""
            SELECT m.group_name, g.vlan_id
            FROM mac_devices m
            JOIN groups g ON m.group_name = g.group_name
            WHERE m.mac_address = $1 AND m.enabled = TRUE
        """, mac)

    if not row:
        raise HTTPException(status_code=403, detail="Bilinmeyen MAC veya yetkisiz")

    # MAB olan cihazları örneğin guest VLAN'a aktarmak için VLAN cevabını dön
    return build_vlan_response(row["vlan_id"])