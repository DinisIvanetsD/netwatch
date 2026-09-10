import re

MAC_PATTERN = re.compile(r"^[0-9A-F]{2}(?::[0-9A-F]{2}){5}$")


def normalize_mac(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().replace("-", ":").upper()
    return candidate if MAC_PATTERN.fullmatch(candidate) else None


def is_locally_administered_mac(value: str | None) -> bool:
    normalized = normalize_mac(value)
    return bool(normalized and int(normalized[:2], 16) & 0b10)


def mac_vendor_hint(value: str | None) -> str | None:
    if is_locally_administered_mac(value):
        return "Private / randomized MAC"
    return None
