from models import Severity

_KEYWORD_RULES: list[tuple[list[str], Severity]] = [
    (["outage", "down", "unreachable", "data loss", "breach"], Severity.CRITICAL),
    (["degraded", "latency spike", "error rate", "failover"], Severity.HIGH),
    (["warning", "retry", "slow", "threshold"], Severity.MEDIUM),
    (["info", "notice", "routine"], Severity.LOW),
]


def classify_severity(
    title: str, description: str, labels: dict[str, str]
) -> Severity:
    text = f"{title} {description}".lower()
    label_sev = labels.get("severity", "").lower()
    for sev in Severity:
        if label_sev == sev.value:
            return sev
    for keywords, severity in _KEYWORD_RULES:
        if any(kw in text for kw in keywords):
            return severity
    return Severity.MEDIUM