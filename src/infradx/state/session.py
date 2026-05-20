from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class Phase(str, Enum):
    CLASSIFY = "CLASSIFY"
    GATHER_SPEC = "GATHER_SPEC"
    DESCRIBE_SYMPTOM = "DESCRIBE_SYMPTOM"
    REQUEST_METRICS = "REQUEST_METRICS"
    ANALYZE = "ANALYZE"
    HYPOTHESIZE = "HYPOTHESIZE"
    REPRODUCE = "REPRODUCE"
    RECOMMEND = "RECOMMEND"


Domain = Literal["server", "network", "disk"] | None


@dataclass
class Hypothesis:
    text: str
    confidence: Literal["HIGH", "MED", "LOW"]
    evidence: str


@dataclass
class SystemSpec:
    os_type: str | None = None
    kernel_version: str | None = None
    deployment_type: str | None = None
    hypervisor: str | None = None
    arch: str | None = None
    vendor_info: str | None = None
    disk_interface: str | None = None
    disk_type: str | None = None


@dataclass
class Symptom:
    started_when: str | None = None
    reproducibility: str | None = None
    error_text: str | None = None
    recent_changes: str | None = None


@dataclass
class Session:
    session_id: str
    phase: Phase = Phase.CLASSIFY
    domain: Domain = None
    spec: SystemSpec = field(default_factory=SystemSpec)
    symptom: Symptom = field(default_factory=Symptom)
    metrics_collected: list[str] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    root_cause: str | None = None
    messages: list[dict] = field(default_factory=list)

    def advance_phase(self) -> None:
        phases = list(Phase)
        current_idx = phases.index(self.phase)
        if current_idx < len(phases) - 1:
            self.phase = phases[current_idx + 1]

    def add_message(self, role: Literal["user", "assistant"], content: str) -> None:
        self.messages.append({"role": role, "content": content})

    def top_hypothesis(self) -> Hypothesis | None:
        high = [h for h in self.hypotheses if h.confidence == "HIGH"]
        return high[0] if high else (self.hypotheses[0] if self.hypotheses else None)
