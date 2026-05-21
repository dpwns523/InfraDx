from __future__ import annotations

from textual import on, events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static
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

_PHASE_REASK = {
    Phase.CLASSIFY: "현재 문제의 도메인(서버/네트워크/디스크/Kubernetes/클라우드)을 다시 분류해주세요.",
    Phase.GATHER_SPEC: "시스템 사양(OS, 커널, 배포 유형 등)을 다시 수집해주세요.",
    Phase.DESCRIBE_SYMPTOM: "현재 증상을 다시 상세히 기술해주세요. 에러 메시지, 발생 시각, 재현율 등을 포함해주세요.",
    Phase.REQUEST_METRICS: "지금 상황에서 수집해야 할 메트릭과 진단 명령어를 다시 알려주세요.",
    Phase.ANALYZE: "지금까지 수집된 데이터를 다시 분석하고 패턴을 정리해주세요.",
    Phase.HYPOTHESIZE: "현재 근거를 바탕으로 가설 목록을 다시 정리하고 신뢰도를 재평가해주세요.",
    Phase.REPRODUCE: "재현 시나리오를 단계별로 다시 정리해서 알려주세요.",
    Phase.RECOMMEND: "지금까지의 분석을 바탕으로 권고사항과 즉각 조치 방법을 다시 알려주세요.",
}


class PhaseClicked(Message):
    """Posted by _PhaseLabel; bubbles up to the app."""
    def __init__(self, phase: Phase) -> None:
        super().__init__()
        self.phase = phase


class _PhaseLabel(Static):
    """Clickable phase step label (Static-based to avoid Button height quirks)."""

    can_focus = True

    def __init__(self, phase: Phase) -> None:
        super().__init__(_PHASE_LABELS[phase], id=f"phase-{phase.value}", markup=True)
        self._phase = phase

    def on_click(self) -> None:
        self.post_message(PhaseClicked(self._phase))

    def on_key(self, event: events.Key) -> None:
        if event.key == "enter":
            self.post_message(PhaseClicked(self._phase))


class SidebarPanel(Widget):
    """Right panel: phase progress, spec summary, hypothesis list."""

    # Alias so app.py can reference SidebarPanel.PhaseClicked
    PhaseClicked = PhaseClicked

    DEFAULT_CSS = """
    SidebarPanel {
        width: 1fr;
        height: 100%;
        border: solid $accent;
        overflow-y: auto;
    }

    SidebarPanel .section-title {
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
        text-style: bold;
        width: 100%;
    }

    SidebarPanel _PhaseLabel {
        height: 1;
        padding: 0 2;
        color: $text-muted;
        width: 100%;
    }

    SidebarPanel _PhaseLabel:hover {
        background: $surface-lighten-1;
        color: $text;
    }

    SidebarPanel _PhaseLabel:focus {
        background: $surface-lighten-1;
    }

    SidebarPanel _PhaseLabel.phase-active {
        color: $success;
        text-style: bold;
    }

    SidebarPanel _PhaseLabel.phase-done {
        color: $text-muted;
    }

    SidebarPanel #spec-summary {
        padding: 0 2;
        color: $text;
    }

    SidebarPanel #hypothesis-display {
        padding: 0 2;
    }

    SidebarPanel #token-gauge {
        padding: 0 2;
        color: $success;
    }

    SidebarPanel #token-label {
        padding: 0 2;
        color: $text-muted;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("── 진행 단계 ──", classes="section-title")
            for phase in Phase:
                yield _PhaseLabel(phase)

            yield Static("── 시스템 정보 ──", classes="section-title")
            yield Static("수집 중...", id="spec-summary")

            yield Static("── 현재 가설 ──", classes="section-title")
            yield Static("가설 없음", id="hypothesis-display")

            yield Static("── 컨텍스트 사용량 ──", classes="section-title")
            yield Static("░" * 20, id="token-gauge", markup=True)
            yield Static("대기 중...", id="token-label")

    @staticmethod
    def _render_token_gauge(used: int, total: int, width: int = 20) -> tuple[str, str]:
        ratio = min(used / total, 1.0) if total > 0 else 0.0
        filled = int(ratio * width)
        color = "green" if ratio < 0.7 else "yellow" if ratio < 0.9 else "red"
        bar = f"[{color}]{'█' * filled}[/][dim]{'░' * (width - filled)}[/dim]"
        label = f"{used:,} / {total:,} ({ratio * 100:.1f}%)"
        return bar, label

    def update_from_session(self, session: Session) -> None:
        phase_order = list(Phase)
        current_idx = phase_order.index(session.phase)

        for i, phase in enumerate(phase_order):
            lbl = self.query_one(f"#phase-{phase.value}", _PhaseLabel)
            lbl.remove_class("phase-active", "phase-done")
            if i < current_idx:
                lbl.update(f"✓ {_PHASE_LABELS[phase]}")
                lbl.add_class("phase-done")
            elif i == current_idx:
                lbl.update(f"→ {_PHASE_LABELS[phase]}")
                lbl.add_class("phase-active")
            else:
                lbl.update(_PHASE_LABELS[phase])

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

        self.query_one("#spec-summary", Static).update(
            "\n".join(spec_lines) if spec_lines else "수집 중..."
        )

        hypo_display = self.query_one("#hypothesis-display", Static)
        if session.hypotheses:
            lines: list[str] = []
            _status_icon = {"validated": "✅", "invalidated": "❌", "investigating": "🔄"}
            _conf_badge = {"HIGH": "🔴", "MED": "🟡", "LOW": "⚪"}
            for h in session.hypotheses:
                s_icon = _status_icon.get(h.status, "🔄")
                c_badge = _conf_badge.get(h.confidence, "")
                lines.append(f"{s_icon} {c_badge} [{h.confidence}] {h.text}")
                if h.evidence:
                    lines.append(f"  └ {h.evidence}")
            hypo_display.update("\n".join(lines))
        elif session.root_cause:
            hypo_display.update(f"✅ {session.root_cause}")
        else:
            hypo_display.update("가설 없음")

        if session.last_prompt_tokens > 0:
            bar, label = self._render_token_gauge(
                session.last_prompt_tokens, session.context_limit
            )
            out_info = f"  출력 {session.total_output_tokens:,}tok"
            self.query_one("#token-gauge", Static).update(bar)
            self.query_one("#token-label", Static).update(label + out_info)
