import re

_DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}\.?$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.?$",
    re.IGNORECASE,
)


def normalize_domain(value: str) -> str:
    domain = value.strip().rstrip(".").lower()
    try:
        ascii_domain = domain.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise ValueError("Domain is not valid") from error
    if not _DOMAIN_PATTERN.fullmatch(ascii_domain):
        raise ValueError("Domain must be a valid fully qualified domain name")
    return ascii_domain
