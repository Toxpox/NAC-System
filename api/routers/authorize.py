import logging
from fastapi import APIRouter, HTTPException
from database import get_db_pool
from models import AuthorizeRequest, is_mac_address, build_vlan_response

logger = logging.getLogger("nac.authorize")

router = APIRouter()

@router.post("/authorize")
async def authorize(req: AuthorizeRequest):
    # FreeRADIUS yetkilendirme (VLAN atama) Endpoint'i
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        # RADIUS MAB: Switch, MAC adresini User-Name attribute'ü olarak gönderir (RFC 2865).
        # Bu yüzden User-Name'in MAC formatında olup olmadığını kontrol ediyoruz.
        caller = req.calling_station_id or ""
        target = req.username if not is_mac_address(req.username) else caller

        # Kullanıcının veya cihazın dahil olduğu ağ grubuna ait dinamik VLAN atamasını getirir
        if is_mac_address(target):
            row = await conn.fetchrow("""
                SELECT g.vlan_id FROM mac_devices m
                JOIN groups g ON m.group_name = g.group_name
                WHERE m.mac_address = $1 AND m.enabled = TRUE
            """, target.upper())
        else:
            row = await conn.fetchrow("""
                SELECT g.vlan_id FROM users u
                JOIN groups g ON u.group_name = g.group_name
                WHERE u.username = $1 AND u.enabled = TRUE
            """, target)

    # Bilinmeyen veya devre dışı cihaz/kullanıcı → guest VLAN'a yönlendir
    if not row:
        logger.info(f"Yetkilendirme profili bulunamadı, guest VLAN atanıyor: {target}")
        guest = await _get_guest_vlan(pool)
        return build_vlan_response(guest)

    return build_vlan_response(row["vlan_id"])


async def _get_guest_vlan(pool) -> int:
    """Guest grubunun VLAN ID'sini getirir. Grup yoksa varsayılan 30 döner."""
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT vlan_id FROM groups WHERE group_name = 'guest'")
    return row["vlan_id"] if row else 30