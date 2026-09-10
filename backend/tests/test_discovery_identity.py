from services.discovery.identity import (
    is_locally_administered_mac,
    mac_vendor_hint,
    normalize_mac,
)


def test_normalizes_valid_mac_addresses() -> None:
    assert normalize_mac("aa-bb-cc-dd-ee-ff") == "AA:BB:CC:DD:EE:FF"
    assert normalize_mac("invalid") is None


def test_identifies_locally_administered_addresses_without_guessing_vendor() -> None:
    assert is_locally_administered_mac("72:4F:56:7B:6E:DD") is True
    assert mac_vendor_hint("72:4F:56:7B:6E:DD") == "Private / randomized MAC"
    assert is_locally_administered_mac("74:9B:E8:A1:B1:62") is False
    assert mac_vendor_hint("74:9B:E8:A1:B1:62") is None
