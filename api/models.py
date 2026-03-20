import re
from ipaddress import ip_address
from typing import Optional
from pydantic import BaseModel, field_validator


def _validate_ip(v: Optional[str]) -> Optional[str]:
    """IP adresi formatını doğrular. Boş/None değerler geçerli sayılır."""
    if not v:
        return v
    try:
        ip_address(v)
    except ValueError:
        raise ValueError(f"Geçersiz IP adresi: {v}")
    return v


class AuthRequest(BaseModel):
    # Doğrulama (Authenticate) için FreeRADIUS'tan gelecek bilgileri tanımlayan model
    username: str
    password: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None

    @field_validator("nas_ip")
    @classmethod
    def check_nas_ip(cls, v):
        return _validate_ip(v)


class AuthorizeRequest(BaseModel):
    # Yetkilendirme (Authorize) isteği için kullanılacak model
    username: str
    nas_ip: Optional[str] = None
    calling_station_id: Optional[str] = None

    @field_validator("nas_ip")
    @classmethod
    def check_nas_ip(cls, v):
        return _validate_ip(v)


class AccountingRequest(BaseModel):
    # Hesap tutma (Accounting) işlemleri için FreeRADIUS'tan gelen paket verilerini tanımlar
    username: str
    session_id: str
    status_type: str

    # FreeRADIUS boş string olarak ("") yollayabildiği için Optional[str | int] yapısıyla hataları engelliyoruz.
    session_time: Optional[str | int] = 0
    input_octets: Optional[str | int] = 0
    output_octets: Optional[str | int] = 0
    nas_ip: Optional[str] = None
    framed_ip: Optional[str] = None
    calling_station_id: Optional[str] = None
    nas_port_id: Optional[str] = None
    terminate_cause: Optional[str] = None

    @field_validator("nas_ip", "framed_ip")
    @classmethod
    def check_ips(cls, v):
        return _validate_ip(v)


class UserCreate(BaseModel):
    # Yeni bir kullanıcı (Örn. admin veya çalışan) oluşturmak için beklenen payload modeli
    username: str
    password: str
    group_name: str


class MacDeviceCreate(BaseModel):
    # MAB (Mac Authentication Bypass) için cihaza özgü modeli tanımlar
    mac_address: str
    group_name: str
    device_type: Optional[str] = None

    @field_validator("mac_address")
    @classmethod
    def validate_mac(cls, v: str) -> str:
        # MAC adresini standart formata (AA:BB:CC:DD:EE:FF) normalize eden Pydantic validatörü
        normalized = v.upper().replace("-", ":").replace(".", ":")
        if not re.match(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", normalized):
            raise ValueError(f"Geçersiz MAC: {v}")
        return normalized


# Sabit derlenmiş Regex kuralı
MAC_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}[:\-]){5}[0-9A-Fa-f]{2}$")


def is_mac_address(value: str) -> bool:
    # Verilen kullanıcı adının MAC adresi olup olmadığını hızlıca kontrol eder
    return bool(MAC_PATTERN.match(value))


def build_vlan_response(vlan_id: int) -> dict:
    # FreeRADIUS'a başarılı yetkilendirmelerde VLAN ID dönüş yapısını hazırlayan standart üretici metot
    return {
        "reply:Tunnel-Type":             {"type": "integer", "value": [13]},
        "reply:Tunnel-Medium-Type":      {"type": "integer", "value": [6]},
        "reply:Tunnel-Private-Group-Id": {"type": "string",  "value": [str(vlan_id)]}
    }
