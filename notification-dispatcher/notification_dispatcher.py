import time
import hashlib
import logging
import asyncio
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from .routing_config import RoutingConfig, ChannelType, RoutingRule

logger = logging.getLogger(__name__)


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class Incident:
    id: str
    title: str
    severity: Severity
    category: str
    description: str = ""
    metadata: dict = field(default_factory=dict)
    correlation_key: str = ""
    dedup_hash: str = ""


@dataclass
class DispatchResult:
    incident_id: str
    channel: ChannelType
    success: bool
    message: str = ""
    timestamp: float = field(default_factory=time.time)


class TokenBucketRateLimiter:
    def __init__(self, rate: float, burst: int):
        self.rate = rate
        self.burst = burst
        self._tokens: dict[str, float] = {}
        self._last: dict[str, float] = {}

    def allow(self, key: str) -> bool:
        now = time.time()
        last = self._last.get(key, now)
        tokens = self._tokens.get(key, float(self.burst))
        elapsed = now - last
        tokens = min(self.burst, tokens + elapsed * self.rate)
        self._last[key] = now
        if tokens >= 1.0:
            self._tokens[key] = tokens - 1.0
            return True
        self._tokens[key] = tokens
        return False


class NotificationDispatcher:
    def __init__(self, config: RoutingConfig, http_client: Optional[httpx.AsyncClient] = None):
        self.config = config
        self._client = http_client or httpx.AsyncClient(timeout=15.0)
        self._owned_client = http_client is None
        self._rate_limiter = TokenBucketRateLimiter(
            rate=config.rate_limit_per_second, burst=config.rate_limit_burst
        )
        self._dispatchers = {
            ChannelType.SLACK: self._dispatch_slack,
            ChannelType.PAGERDUTY: self._dispatch_pagerduty,
            ChannelType.EMAIL: self._dispatch_email,
        }

    async def close(self):
        if self._owned_client:
            await self._client.aclose()

    def _resolve_channels(self, incident: Incident) -> list[RoutingRule]:
        matched: list[RoutingRule] = []
        for rule in self.config.rules:
            if rule.severities and incident.severity not in rule.severities:
                continue
            if rule.categories and incident.category not in rule.categories:
                continue
            matched.append(rule)
        if not matched:
            default = self.config.default_rule
            if default:
                matched.append(default)
        return matched

    async def dispatch(self, incident: Incident) -> list[DispatchResult]:
        rules = self._resolve_channels(incident)
        results: list[DispatchResult] = []
        tasks = []
        for rule in rules:
            rate_key = f"{rule.channel.value}:{incident.category}"
            if not self._rate_limiter.allow(rate_key):
                results.append(DispatchResult(
                    incident_id=incident.id, channel=rule.channel,
                    success=False, message="rate_limited",
                ))
                continue
            handler = self._dispatchers.get(rule.channel)
            if handler:
                tasks.append(handler(incident, rule))
        if tasks:
            task_results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in task_results:
                if isinstance(r, Exception):
                    logger.error("Dispatch failed: %s", r)
                    results.append(DispatchResult(
                        incident_id=incident.id, channel=ChannelType.SLACK,
                        success=False, message=str(r),
                    ))
                else:
                    results.append(r)
        return results

    async def _dispatch_slack(self, incident: Incident, rule: RoutingRule) -> DispatchResult:
        url = rule.webhook_url or self.config.slack_webhook_url
        if not url:
            return DispatchResult(incident.id, ChannelType.SLACK, False, "no_webhook_url")
        payload = {
            "text": f"[{incident.severity.value.upper()}] {incident.title}",
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn",
                 "text": f"*Severity*: {incident.severity.value}\n*Category*: {incident.category}\n*Description*: {incident.description}"}},
                {"type": "context", "elements": [{"type": "mrkdwn", "text": f"Incident ID: `{incident.id}`"}]},
            ],
        }
        try:
            resp = await self._client.post(url, json=payload)
            ok = resp.status_code == 200
            return DispatchResult(incident.id, ChannelType.SLACK, ok, resp.text[:200])
        except Exception as exc:
            return DispatchResult(incident.id, ChannelType.SLACK, False, str(exc))

    async def _dispatch_pagerduty(self, incident: Incident, rule: RoutingRule) -> DispatchResult:
        url = self.config.pagerduty_events_url
        key = rule.routing_key or self.config.pagerduty_routing_key
        if not url or not key:
            return DispatchResult(incident.id, ChannelType.PAGERDUTY, False, "no_pd_config")
        payload = {
            "routing_key": key,
            "event_action": "trigger",
            "payload": {
                "summary": incident.title,
                "severity": incident.severity.value,
                "source": incident.metadata.get("source", "incident-triage"),
                "component": incident.category,
                "group": incident.correlation_key or incident.id,
                "class": incident.category,
                "custom_details": incident.metadata,
            },
        }
        try:
            resp = await self._client.post(url, json=payload, headers={"Content-Type": "application/json"})
            ok = 200 <= resp.status_code < 300
            return DispatchResult(incident.id, ChannelType.PAGERDUTY, ok, resp.text[:200])
        except Exception as exc:
            return DispatchResult(incident.id, ChannelType.PAGERDUTY, False, str(exc))

    async def _dispatch_email(self, incident: Incident, rule: RoutingRule) -> DispatchResult:
        recipients = rule.email_recipients or self.config.default_email_recipients
        if not recipients:
            return DispatchResult(incident.id, ChannelType.EMAIL, False, "no_recipients")
        subject = f"[{incident.severity.value.upper()}] {incident.title}"
        body = (
            f"Incident ID: {incident.id}\n"
            f"Severity: {incident.severity.value}\n"
            f"Category: {incident.category}\n"
            f"Correlation: {incident.correlation_key}\n\n"
            f"{incident.description}\n"
        )
        logger.info("Email to %s: %s", recipients, subject)
        return DispatchResult(incident.id, ChannelType.EMAIL, True, f"queued:{','.join(recipients)}")