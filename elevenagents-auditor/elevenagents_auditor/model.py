"""Core data structures shared by rules and reports."""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SEVERITY_WEIGHT = {"critical": 5, "high": 3, "medium": 2, "low": 1}
SEVERITY_ORDER = ["critical", "high", "medium", "low"]

# Status values: "pass", "partial" (half credit), "fail", "na" (not applicable).
STATUS_CREDIT = {"pass": 1.0, "partial": 0.5, "fail": 0.0}


@dataclass
class Text:
    """A bilingual message."""

    es: str
    en: str

    def get(self, lang: str) -> str:
        return self.es if lang == "es" else self.en


@dataclass
class RuleResult:
    rule_id: str
    dimension: str
    severity: str
    status: str
    title: Text
    finding: Text
    recommendation: Optional[Text] = None
    evidence: str = ""

    @property
    def weight(self) -> int:
        return SEVERITY_WEIGHT[self.severity]

    @property
    def is_gap(self) -> bool:
        return self.status in ("fail", "partial")


@dataclass
class DimensionScore:
    key: str
    name: Text
    score: Optional[float]  # 0-100, None when not applicable
    results: List[RuleResult] = field(default_factory=list)


@dataclass
class AuditReport:
    agent_name: str
    agent_id: str
    overall: Optional[float]
    dimensions: List[DimensionScore]
    context_notes: List[Text] = field(default_factory=list)
    meta: Dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        """A failed critical check blocks 'ready to scale', whatever the average says."""
        return any(r.severity == "critical" and r.status == "fail" for d in self.dimensions for r in d.results)

    def gaps(self) -> List[RuleResult]:
        out = [r for d in self.dimensions for r in d.results if r.is_gap]
        out.sort(key=lambda r: (SEVERITY_ORDER.index(r.severity), r.status == "partial"))
        return out


def dig(data: Any, path: str, default: Any = None) -> Any:
    """Safe nested lookup: dig(cfg, "conversation_config.agent.language")."""
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return default
    return default if cur is None else cur
