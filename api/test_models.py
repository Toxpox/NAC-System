"""
Unit testler — models.py fonksiyonlarının doğruluğunu garanti altına alır.
Dış bağımlılık gerektirmez (veritabanı, Redis yok), saf mantık testleri.
"""
import pytest
from models import is_mac_address, build_vlan_response, _validate_ip


# ---------- is_mac_address ----------

class TestIsMacAddress:
    def test_valid_colon_separated(self):
        assert is_mac_address("AA:BB:CC:DD:EE:FF") is True

    def test_valid_lowercase(self):
        assert is_mac_address("aa:bb:cc:dd:ee:ff") is True

    def test_valid_mixed_case(self):
        assert is_mac_address("aA:bB:cC:dD:eE:fF") is True

    def test_valid_dash_separated(self):
        assert is_mac_address("AA-BB-CC-DD-EE-FF") is True

    def test_invalid_username(self):
        assert is_mac_address("admin") is False

    def test_invalid_short_mac(self):
        assert is_mac_address("AA:BB:CC") is False

    def test_invalid_empty(self):
        assert is_mac_address("") is False

    def test_invalid_with_extra_chars(self):
        assert is_mac_address("AA:BB:CC:DD:EE:FG") is False


# ---------- build_vlan_response ----------

class TestBuildVlanResponse:
    def test_returns_correct_tunnel_type(self):
        resp = build_vlan_response(20)
        assert resp["reply:Tunnel-Type"]["value"] == [13]

    def test_returns_correct_medium_type(self):
        resp = build_vlan_response(20)
        assert resp["reply:Tunnel-Medium-Type"]["value"] == [6]

    def test_returns_correct_vlan_id(self):
        resp = build_vlan_response(20)
        assert resp["reply:Tunnel-Private-Group-Id"]["value"] == ["20"]

    def test_vlan_id_as_string(self):
        # VLAN ID her zaman string olarak dönmeli (RADIUS attribute formatı)
        resp = build_vlan_response(10)
        assert isinstance(resp["reply:Tunnel-Private-Group-Id"]["value"][0], str)

    def test_different_vlan_ids(self):
        for vlan in [10, 20, 30, 100, 4094]:
            resp = build_vlan_response(vlan)
            assert resp["reply:Tunnel-Private-Group-Id"]["value"] == [str(vlan)]


# ---------- _validate_ip ----------

class TestValidateIp:
    def test_valid_ipv4(self):
        assert _validate_ip("192.168.1.1") == "192.168.1.1"

    def test_valid_loopback(self):
        assert _validate_ip("127.0.0.1") == "127.0.0.1"

    def test_none_returns_none(self):
        assert _validate_ip(None) is None

    def test_empty_returns_empty(self):
        assert _validate_ip("") == ""

    def test_invalid_ip_raises(self):
        with pytest.raises(ValueError, match="Geçersiz IP"):
            _validate_ip("999.999.999.999")

    def test_invalid_string_raises(self):
        with pytest.raises(ValueError, match="Geçersiz IP"):
            _validate_ip("not-an-ip")
