from services.activity.classification import classify_domain


def test_domain_classification_matches_subdomains_without_false_suffixes() -> None:
    assert classify_domain("www.youtube.com") == "streaming"
    assert classify_domain("cdn.discord.com.") == "communication"
    assert classify_domain("notyoutube.com") == "other"
    assert classify_domain("unknown.example") == "other"
