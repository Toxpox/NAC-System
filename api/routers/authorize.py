from fastapi import APIRouter, HTTPException
from database import get_db_pool
from models import AuthorizeRequest, is_mac_address, build_vlan_response

router = APIRouter()

@router.post("/authorize")
async def authorize(req: AuthorizeRequest):
    # FreeRADIUS yetkilendirme (VLAN atama) Endpoint'i
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        caller = req.calling_station_id or ""
        target = caller if is_mac_address(caller) else req.username
        
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

    if not row:
        raise HTTPException(status_code=403, detail="Yetkilendirme profili bulunamadi")
        
    return build_vlan_response(row["vlan_id"])