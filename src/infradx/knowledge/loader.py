from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

_DATA_DIR = Path(__file__).parent / "data"


@dataclass
class KnowledgeEntry:
    id: str
    title: str
    domain: str
    os: str | None
    severity: str
    category: str
    keywords: list[str]
    symptoms: list[str]
    diagnosis_commands: list[dict]
    root_causes: list[str]
    fix_immediate: list[str]
    fix_permanent: list[str]
    prevention: list[str]
    dmesg_patterns: list[str] = field(default_factory=list)
    errpt_patterns: list[str] = field(default_factory=list)
    diagnosis_hints: list[str] = field(default_factory=list)

    def to_context_block(self) -> str:
        """Format entry as a compact context block for injection into AI prompt."""
        severity_badge = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "⚪"}.get(
            self.severity, ""
        )
        lines = [
            f"### [{self.id}] {severity_badge} {self.title}",
            f"**관련 증상:** {' / '.join(self.symptoms[:3])}",
        ]
        if self.dmesg_patterns:
            lines.append(f"**dmesg 패턴:** `{'` `'.join(self.dmesg_patterns[:3])}`")
        if self.errpt_patterns:
            lines.append(f"**errpt 패턴:** `{'` `'.join(self.errpt_patterns[:2])}`")
        lines.append(f"**주요 원인:** {' / '.join(self.root_causes[:2])}")
        lines.append(f"**즉각 조치:** {self.fix_immediate[0]}" if self.fix_immediate else "")
        if self.diagnosis_hints:
            lines.append(f"**진단 힌트:** {self.diagnosis_hints[0]}")
        return "\n".join(l for l in lines if l)


def _parse_fix(fix: Any) -> tuple[list[str], list[str]]:
    if not fix or not isinstance(fix, dict):
        return [], []
    immediate = fix.get("immediate", []) or []
    permanent = fix.get("permanent", []) or []
    return (
        immediate if isinstance(immediate, list) else [immediate],
        permanent if isinstance(permanent, list) else [permanent],
    )


def _load_yaml_file(path: Path) -> list[KnowledgeEntry]:
    if yaml is None:
        raise RuntimeError("PyYAML이 설치되지 않았습니다. pip install pyyaml")

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    top_domain = data.get("domain", "unknown")
    top_os = data.get("os")
    entries: list[KnowledgeEntry] = []

    for issue in data.get("issues", []):
        imm, perm = _parse_fix(issue.get("fix"))
        cmds = issue.get("diagnosis_commands", []) or []

        entries.append(
            KnowledgeEntry(
                id=issue.get("id", ""),
                title=issue.get("title", ""),
                domain=top_domain,
                os=top_os,
                severity=issue.get("severity", "medium"),
                category=issue.get("category", ""),
                keywords=[k.lower() for k in (issue.get("keywords") or [])],
                symptoms=issue.get("symptoms") or [],
                diagnosis_commands=cmds,
                root_causes=issue.get("root_causes") or [],
                fix_immediate=imm,
                fix_permanent=perm,
                prevention=issue.get("prevention") or [],
                dmesg_patterns=issue.get("dmesg_patterns") or [],
                errpt_patterns=issue.get("errpt_patterns") or [],
                diagnosis_hints=issue.get("diagnosis_hints") or [],
            )
        )
    return entries


class KnowledgeBase:
    """In-memory knowledge base loaded from YAML data files."""

    def __init__(self) -> None:
        self._entries: list[KnowledgeEntry] = []
        self._loaded = False

    def load(self) -> None:
        if self._loaded:
            return
        if not _DATA_DIR.exists():
            return
        for yaml_file in sorted(_DATA_DIR.glob("*.yaml")):
            try:
                self._entries.extend(_load_yaml_file(yaml_file))
            except Exception as e:
                # Non-fatal: skip broken files
                print(f"[KB] {yaml_file.name} 로드 실패: {e}")
        self._loaded = True

    def search(
        self,
        query: str,
        domain: str | None = None,
        os_type: str | None = None,
        top_n: int = 3,
    ) -> list[KnowledgeEntry]:
        """
        Keyword search over title, keywords, symptoms, dmesg_patterns.
        Returns top_n entries ranked by match score.
        """
        if not self._loaded:
            self.load()

        query_tokens = re.split(r"[\s,]+", query.lower())
        scored: list[tuple[float, KnowledgeEntry]] = []

        for entry in self._entries:
            # Domain/OS filter
            if domain and entry.domain != domain and not (
                domain == "server" and entry.domain == "server"
            ):
                continue
            if os_type and entry.os and entry.os != os_type:
                continue

            score = self._score(query_tokens, entry)
            if score > 0:
                scored.append((score, entry))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:top_n]]

    def _score(self, tokens: list[str], entry: KnowledgeEntry) -> float:
        score = 0.0
        def _safe_join(items: list) -> str:
            return " ".join(str(i) for i in items if isinstance(i, (str, int, float)))

        searchable = {
            "title": (entry.title.lower(), 3.0),
            "keywords": (_safe_join(entry.keywords), 2.5),
            "symptoms": (_safe_join(entry.symptoms).lower(), 2.0),
            "dmesg": (_safe_join(entry.dmesg_patterns).lower(), 2.0),
            "errpt": (_safe_join(entry.errpt_patterns).lower(), 2.0),
            "root_causes": (_safe_join(entry.root_causes).lower(), 1.0),
            "category": (entry.category.lower(), 1.5),
        }
        for token in tokens:
            if len(token) < 2:
                continue
            for _field, (text, weight) in searchable.items():
                if token in text:
                    score += weight
                    # Exact keyword match bonus
                    if token in entry.keywords:
                        score += 1.0
        # Severity boost
        severity_bonus = {"critical": 0.3, "high": 0.2, "medium": 0.1}.get(entry.severity, 0)
        if score > 0:
            score += severity_bonus
        return score

    def get_by_id(self, entry_id: str) -> KnowledgeEntry | None:
        for e in self._entries:
            if e.id == entry_id:
                return e
        return None

    def all_for_domain(self, domain: str, os_type: str | None = None) -> list[KnowledgeEntry]:
        return [
            e for e in self._entries
            if e.domain == domain and (os_type is None or e.os == os_type or e.os is None)
        ]

    @property
    def entry_count(self) -> int:
        return len(self._entries)


# Singleton instance
_kb: KnowledgeBase | None = None


def get_knowledge_base() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
        _kb.load()
    return _kb
