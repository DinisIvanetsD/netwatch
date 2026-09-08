from collections.abc import Iterable
from dataclasses import dataclass

import tldextract

SERVICE_DOMAINS: dict[str, tuple[str, ...]] = {
    "YouTube": ("youtube.com", "youtu.be", "googlevideo.com", "ytimg.com"),
    "TikTok": ("tiktok.com", "tiktokcdn.com", "byteoversea.com"),
    "Roblox": ("roblox.com", "rbxcdn.com"),
    "Discord": ("discord.com", "discordapp.com", "discordapp.net", "discord.gg"),
    "Instagram": ("instagram.com", "cdninstagram.com"),
    "Netflix": ("netflix.com", "nflxvideo.net", "nflximg.net", "nflxso.net"),
    "Spotify": ("spotify.com", "scdn.co", "spotifycdn.com"),
    "Steam": ("steampowered.com", "steamcommunity.com", "steamcontent.com"),
    "Facebook": ("facebook.com", "fbcdn.net", "messenger.com"),
    "WhatsApp": ("whatsapp.com", "whatsapp.net"),
    "Twitch": ("twitch.tv", "ttvnw.net"),
    "Xbox": ("xboxlive.com", "xbox.com"),
    "PlayStation": ("playstation.net", "playstation.com"),
    "Google": ("google.com", "googleapis.com", "gstatic.com"),
    "Wikipedia": ("wikipedia.org", "wikimedia.org"),
    "Amazon": ("amazon.com", "amazonaws.com"),
}

SERVICE_CATEGORIES = {
    "YouTube": "streaming",
    "TikTok": "social_media",
    "Roblox": "gaming",
    "Discord": "communication",
    "Instagram": "social_media",
    "Netflix": "streaming",
    "Spotify": "streaming",
    "Steam": "gaming",
    "Facebook": "social_media",
    "WhatsApp": "communication",
    "Twitch": "streaming",
    "Xbox": "gaming",
    "PlayStation": "gaming",
    "Google": "search",
    "Wikipedia": "education",
    "Amazon": "shopping",
}

BLOCK_REASON_CATEGORIES = {
    "FilteredParental": "adult_content",
    "FilteredSafeBrowsing": "security",
    "FilteredBlockedService": "blocked_service",
    "FilteredBlackList": "custom_or_filter_list",
}

_extractor = tldextract.TLDExtract(suffix_list_urls=())


@dataclass(frozen=True, slots=True)
class DomainClassification:
    registered_domain: str
    service: str | None
    category: str
    inferred: bool


def _matches(domain: str, candidates: Iterable[str]) -> bool:
    return any(domain == candidate or domain.endswith(f".{candidate}") for candidate in candidates)


class DomainClassificationService:
    """Classify DNS names as inferred services without claiming content visibility."""

    def classify(self, domain: str, *, block_reason: str | None = None) -> DomainClassification:
        normalized = domain.lower().rstrip(".")
        extracted = _extractor(normalized)
        registered_domain = extracted.top_domain_under_public_suffix or normalized
        for service, candidates in SERVICE_DOMAINS.items():
            if _matches(normalized, candidates):
                return DomainClassification(
                    registered_domain=registered_domain,
                    service=service,
                    category=SERVICE_CATEGORIES[service],
                    inferred=True,
                )
        return DomainClassification(
            registered_domain=registered_domain,
            service=None,
            category=BLOCK_REASON_CATEGORIES.get(block_reason or "", "other"),
            inferred=False,
        )


domain_classification_service = DomainClassificationService()


def classify_domain(domain: str) -> str:
    """Compatibility helper for callers that only need the category."""

    return domain_classification_service.classify(domain).category
