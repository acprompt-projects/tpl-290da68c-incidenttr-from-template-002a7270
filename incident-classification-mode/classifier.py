import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Severity(Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Category(Enum):
    INFRA = "infra"
    APP = "app"
    SECURITY = "security"
    NETWORK = "network"


@dataclass
class TriageLabel:
    severity: Severity
    category: Category
    confidence: float
    rule_ids: list[str] = field(default_factory=list)
    overrides: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "category": self.category.value,
            "confidence": round(self.confidence, 3),
            "rule_ids": self.rule_ids,
            "overrides": self.overrides,
        }


@dataclass
class ClassificationRule:
    rule_id: str
    category: Category
    severity: Severity
    priority: int
    pattern: Optional[str] = None
    keywords: Optional[list[str]] = None
    metric_threshold: Optional[dict[str, Any]] = None
    confidence_base: float = 1.0

    def matches(self, incident: dict[str, Any]) -> bool:
        text = f"{incident.get('title', '')} {incident.get('description', '')}".lower()
        if self.pattern and not re.search(self.pattern, text, re.IGNORECASE):
            return False
        if self.keywords:
            if not any(kw.lower() in text for kw in self.keywords):
                return False
        if self.metric_threshold:
            metrics = incident.get("metrics", {})
            field = self.metric_threshold.get("field", "")
            op = self.metric_threshold.get("op", ">=")
            value = self.metric_threshold.get("value", 0)
            actual = metrics.get(field)
            if actual is None:
                return False
            if op == ">=" and not (actual >= value):
                return False
            if op == ">" and not (actual > value):
                return False
            if op == "<=" and not (actual <= value):
                return False
            if op == "<" and not (actual < value):
                return False
        return True


DEFAULT_RULES: list[ClassificationRule] = [
    ClassificationRule("SEC-BRUTE-01", Category.SECURITY, Severity.P1, 10,
                        keywords=["brute force", "credential stuffing", "auth explosion"],
                        pattern=r"brute.?force|credential.?stuff|auth.*explosion"),
    ClassificationRule("SEC-DATA-01", Category.SECURITY, Severity.P1, 10,
                        keywords=["data exfiltration", "data breach", "leak"],
                        pattern=r"exfiltrat|data.?breach|leak"),
    ClassificationRule("SEC-MALWARE-01", Category.SECURITY, Severity.P2, 20,
                        keywords=["malware", "ransomware", "cryptominer"],
                        pattern=r"malware|ransomware|crypto.?miner"),
    ClassificationRule("SEC-VULN-01", Category.SECURITY, Severity.P3, 30,
                        keywords=["vulnerability", "cve", "exploit"],
                        pattern=r"cve|vuln|exploit"),
    ClassificationRule("INFRA-OUT-01", Category.INFRA, Severity.P1, 10,
                        keywords=["outage", "down", "unreachable"],
                        pattern=r"\b(outage|down|unreachable)\b",
                        metric_threshold={"field": "affected_hosts", "op": ">=", "value": 10}),
    ClassificationRule("INFRA-DISK-01", Category.INFRA, Severity.P2, 20,
                        keywords=["disk", "storage", "capacity"],
                        pattern=r"disk.*(full|crit)|storage.*(full|crit)|capacity",
                        metric_threshold={"field": "disk_pct", "op": ">=", "value": 90}),
    ClassificationRule("INFRA-CPU-01", Category.INFRA, Severity.P2, 20,
                        keywords=["cpu", "load", "throttle"],
                        pattern=r"cpu.*(spike|high|crit)|load.*(high|avg)",
                        metric_threshold={"field": "cpu_pct", "op": ">=", "value": 90}),
    ClassificationRule("INFRA-MEM-01", Category.INFRA, Severity.P3, 30,
                        keywords=["memory", "oom", "ram"],
                        pattern=r"memory|oom|ram.*(high|crit)",
                        metric_threshold={"field": "mem_pct", "op": ">=", "value": 85}),
    ClassificationRule("INFRA-SVC-01", Category.INFRA, Severity.P3, 30,
                        keywords=["service restart", "service crash"],
                        pattern=r"service.*(restart|crash|fail)"),
    ClassificationRule("NET-LINK-01", Category.NETWORK, Severity.P1, 10,
                        keywords=["link down", "network partition", "split brain"],
                        pattern=r"link.?down|network.?partition|split.?brain"),
    ClassificationRule("NET-LAT-01", Category.NETWORK, Severity.P2, 20,
                        keywords=["latency", "packet loss", "timeout"],
                        pattern=r"latency|packet.?loss|timeout",
                        metric_threshold={"field": "latency_ms", "op": ">=", "value": 500}),
    ClassificationRule("NET-DNS-01", Category.NETWORK, Severity.P3, 30,
                        keywords=["dns", "resolution failure"],
                        pattern=r"dns.*(fail|error|timeout)|resolution.?fail"),
    ClassificationRule("APP-ERR-01", Category.APP, Severity.P2, 20,
                        keywords=["error rate", "5xx", "exception spike"],
                        pattern=r"error.?rate|5xx|exception.?spike",
                        metric_threshold={"field": "error_rate", "op": ">=", "value": 10}),
    ClassificationRule("APP-ERR-02", Category.APP, Severity.P3, 30,
                        keywords=["error rate", "5xx", "exception"],
                        pattern=r"error.?rate|5xx|exception",
                        metric_threshold={"field": "error_rate", "op": ">=", "value": 5}),
    ClassificationRule("APP-DEP-01", Category.APP, Severity.P3, 30,
                        keywords=["deployment", "rollback", "failed deploy"],
                        pattern=r"deploy.*(fail|rollback)|rollback"),
    ClassificationRule("APP-LOG-01", Category.APP, Severity.P4, 40,
                        keywords=["log", "warning", "degraded"],
                        pattern=r"log.*(warn|flood)|degraded"),
    ClassificationRule("FALLBACK-01", Category.APP, Severity.P4, 999,
                        confidence_base=0.3),
]


class IncidentClassifier:
    def __init__(self, rules: Optional[list[ClassificationRule]] = None):
        self.rules: list[ClassificationRule] = sorted(
            rules or DEFAULT_RULES, key=lambda r: r.priority
        )

    def classify(self, incident: dict[str, Any]) -> TriageLabel:
        matched: list[ClassificationRule] = []
        for rule in self.rules:
            if rule.matches(incident):
                matched.append(rule)
                if rule.severity == Severity.P1 and rule.priority <= 10:
                    break

        if not matched:
            fallback = next(r for r in self.rules if r.rule_id == "FALLBACK-01")
            matched = [fallback]

        best = matched[0]
        confidence = best.confidence_base
        if len(matched) > 1:
            confidence = min(1.0, confidence + 0.1 * (len(matched) - 1))

        severity = best.severity
        explicit = incident.get("severity")
        if explicit and isinstance(explicit, str) and explicit.startswith("P"):
            try:
                override_sev = Severity(explicit.upper())
                severity = override_sev
                confidence = min(1.0, confidence + 0.15)
            except ValueError:
                pass

        return TriageLabel(
            severity=severity,
            category=best.category,
            confidence=confidence,
            rule_ids=[r.rule_id for r in matched],
        )