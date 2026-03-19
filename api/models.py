import re
from typing import Optional
from pydantic import BaseModel

class AuthRequest(BaseModel):
    username: str
    password: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None

class AuthorizeRequest(BaseModel):
    username: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None

class AccountingRequest(BaseModel):
    username: str
    session_id: str
    status_type: str
    session_time: Optional[str | int] = 0
    input_octets: Optional[str | int] = 0
    output_octets: Optional[str | int] = 0
    nas_ip: Optional[str] = None
    framed_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    nas_port_id: Optional[str] = None
    terminate_cause: Optional[str] = None

MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$")

def is_mac_address(value: str) -> bool:
    return bool(MAC_PATTERN.match(value))

def build_vlan_response(vlan_id: int) -> dict:
    return {
        "reply:Tunnel-Type":             {"type": "integer", "value": [13]},
        "reply:Tunnel-Medium-Type":      {"type": "integer", "value": [6]},
        "reply:Tunnel-Private-Group-Id": {"type": "string",  "value": [str(vlan_id)]}
    }
