from __future__ import annotations

from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Label
from textual.containers import Vertical

from infradx.state.session import Session, Phase


_PHASE_LABELS = {
    Phase.CLASSIFY: "1. 분류",
    Phase.GATHER_SPEC: "2. 스펙 수집",
    Phase.DESCRIBE_SYMPTOM: "3. 증상 기술",
    Phase.REQUEST_METRICS: "4. 메트릭 요청",
    Phase.ANALYZE: "5. 분석",
    Phase.HYPOTHESIZE: "6. 가설 확정",
    Phase.REPRODUCE: "7. 재현 시나리오",
    Phase.RECOMMEND: "8. 권고사항",
}


class SidebarPanel(Widget):
    """Right panel: current phase, spec summary, top hypothesis."""

    DEFAULT_CSS = """
    SidebarPanel {
        width: 1fr;
        height: 100%;
        border: solid $accent;
    }

    SidebarPanel .section-title {
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
        text-style: bold;
    }

    SidebarPanel .phase-item {
        padding: 0 2;
        color: $text-muted;
    }

    SidebarPanel .phase-active {
        color: $success;
        text-style: bold;
    }

    SidebarPanel .spec-value {
        padding: 0 2;
        color: $text;
    }

    SidebarPanel .hypothesis-high {
        padding: 0 2;
        color: $warning;
    }

    SidebarPanel .hypothesis-med {
        padding: 0 2;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label("── 진행 단계 ──", classes="section-title")
            for phase, label in _PHASE_LABELS.items():
                yield Label(label, id=f"phase-{phase.value}", classes="phase-item")

            yield Label("── 시스템 정보 ──", classes="section-title")
            yield Static("", id="spec-summary")

            yield Label("── 현재 가설 ──", classes="section-title")
            yield Static("가설 없음", id="hypothesis-display")

    def update_from_session(self, session: Session) -> None:
        # Update phase highlights
        for phase in Phase:
            label = self.query_one(f"#phase-{phase.value}", Label)
            if phase == session.phase:
                label.add_class("phase-active")
                label.remove_class("phase-item")
            else:
                label.remove_class("phase-active")
                label.add_class("phase-item")

        # Update spec summary
        spec = session.spec
        spec_lines: list[str] = []
        if session.domain:
            domain_label = {
                "server": "서버", "network": "네트워크", "disk": "디스크",
                "kubernetes": "Kubernetes", "cloud": "퍼블릭 클라우드",
            }.get(session.domain, session.domain)
            spec_lines.append(f"도메인: {domain_label}")
        if spec.os_type:
            spec_lines.append(f"OS: {spec.os_type}")
        if spec.kernel_version:
            spec_lines.append(f"커널: {spec.kernel_version}")
        if spec.deployment_type:
            spec_lines.append(f"유형: {spec.deployment_type}")
        if spec.k8s_distribution:
            spec_lines.append(f"K8s: {spec.k8s_distribution} {spec.k8s_version or ''}")
        if spec.k8s_problem_scope:
            spec_lines.append(f"범위: {spec.k8s_problem_scope}")
        if spec.cloud_provider:
            spec_lines.append(f"Cloud: {spec.cloud_provider.upper()}")
        if spec.cloud_service:
            spec_lines.append(f"서비스: {spec.cloud_service}")
        if spec.cloud_region:
            spec_lines.append(f"리전: {spec.cloud_region}")

        spec_display = self.query_one("#spec-summary", Static)
        spec_display.update("\n".join(spec_lines) if spec_lines else "수집 중...")

        # Update hypotheses
        hypo_display = self.query_one("#hypothesis-display", Static)
        if session.hypotheses:
            lines = []
            for h in session.hypotheses[:3]:
                badge = {"HIGH": "🔴", "MED": "🟡", "LOW": "⚪"}.get(h.confidence, "")
                lines.append(f"{badge} [{h.confidence}] {h.text[:40]}")
            hypo_display.update("\n".join(lines))
        elif session.root_cause:
            hypo_display.update(f"✅ {session.root_cause[:60]}")
        else:
            hypo_display.update("가설 없음")
