from enum import Enum
from dataclasses import dataclass, field
from typing import Optional


class ChannelType(str, Enum):
    SLACK = "slack"
    PAGERDUTY = "pagerduty"
    EMAIL = "email"


@dataclass
class RoutingRule:
    channel: ChannelType
    severities: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    webhook_url: Optional[str] = None
    routing_key: Optional[str] = None
    email_recipients: list[str] = field(default_factory=list)
    priority: int = 0


@dataclass
class RoutingConfig:
    rules: list[RoutingRule] = field(default_factory=list)
    default_rule: Optional[RoutingRule] = None
    slack_webhook_url: Optional[str] = None
    pagerduty_events_url: str = "https://events.pagerduty.com/v2/enqueue"
    pagerduty_routing_key: Optional[str] = None
    default_email_recipients: list[str] = field(default_factory=list)
    rate_limit_per_second: float = 5.0
    rate_limit_burst: int = 10

    @classmethod
    def from_dict(cls, data: dict) -> "RoutingConfig":
        rules = []
        for r in data.get("rules", []):
            rules.append(RoutingRule(
                channel=ChannelType(r["channel"]),
                severities=r.get("severities", []),
                categories=r.get("categories", []),
                webhook_url=r.get("webhook_url"),
                routing_key=r.get("routing_key"),
                email_recipients=r.get("email_recipients", []),
                priority=r.get("priority", 0),
            ))
        default = None
        if "default_rule" in data and data["default_rule"]:
            d = data["default_rule"]
            default = RoutingRule(
                channel=ChannelType(d["channel"]),
                severities=d.get("severities", []),
                categories=d.get("categories", []),
                webhook_url=d.get("webhook_url"),
                routing_key=d.get("routing_key"),
                email_recipients=d.get("email_recipients", []),
            )
        return cls(
            rules=rules,
            default_rule=default,
            slack_webhook_url=data.get("slack_webhook_url"),
            pagerduty_events_url=data.get("pagerduty_events_url", "https://events.pagerduty.com/v2/enqueue"),
            pagerduty_routing_key=data.get("pagerduty_routing_key"),
            default_email_recipients=data.get("default_email_recipients", []),
            rate_limit_per_second=data.get("rate_limit_per_second", 5.0),
            rate_limit_burst=data.get("rate_limit_burst", 10),
        )


def default_config() -> RoutingConfig:
    return RoutingConfig(
        rules=[
            RoutingRule(channel=ChannelType.PAGERDUTY, severities=["critical", "high"], categories=[], priority=1),
            RoutingRule(channel=ChannelType.SLACK, severities=["critical", "high", "medium"], categories=[], priority=2),
            RoutingRule(channel=ChannelType.EMAIL, severities=["medium", "low", "info"], categories=["security", "compliance"], priority=3),
        ],
        default_rule=RoutingRule(channel=ChannelType.SLACK, severities=[], categories=[]),
        rate_limit_per_second=5.0,
        rate_limit_burst=10,
    )