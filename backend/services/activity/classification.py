from collections.abc import Iterable

CATEGORY_DOMAINS: dict[str, tuple[str, ...]] = {
    "social": ("facebook.com", "instagram.com", "tiktok.com", "x.com", "twitter.com"),
    "streaming": ("youtube.com", "netflix.com", "primevideo.com", "twitch.tv", "spotify.com"),
    "gaming": ("steampowered.com", "steamcommunity.com", "epicgames.com", "xboxlive.com"),
    "communication": ("discord.com", "whatsapp.com", "telegram.org", "zoom.us"),
    "shopping": ("amazon.com", "ebay.com", "aliexpress.com"),
    "education": ("wikipedia.org", "khanacademy.org", "coursera.org"),
}


def _matches(domain: str, candidates: Iterable[str]) -> bool:
    return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in candidates)


def classify_domain(domain: str) -> str:
    normalized = domain.lower().rstrip(".")
    for category, candidates in CATEGORY_DOMAINS.items():
        if _matches(normalized, candidates):
            return category
    return "other"
