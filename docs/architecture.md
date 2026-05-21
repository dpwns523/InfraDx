# InfraDx — Architecture

## 시스템 아키텍처

```mermaid
graph TD
    User["👤 사용자"]

    subgraph TUI ["Textual TUI  (src/infradx/tui/)"]
        App["app.py\nInfraDxApp"]
        Chat["widgets/chat.py\nChatPanel\n─────────────\n채팅 로그\n📊 메트릭 분석\n🔍 가설 업데이트\n📋 결론 도출\n입력창"]
        Sidebar["widgets/sidebar.py\nSidebarPanel\n─────────────\n진행 단계\n시스템 정보\n가설 목록 + 상태"]
    end

    subgraph Agent ["Agent Core  (src/infradx/agent/)"]
        Core["core.py\nAgentCore\n─────────────\nstream_response()\n_parse_hypotheses()\n_parse_root_cause()\n_build_kb_context()"]
    end

    subgraph Backends ["AI Backend"]
        direction LR
        Anthropic["_AnthropicBackend\nclaude-sonnet-4-6"]
        OpenAI["_OpenAIBackend\ngpt-4o / Codex ✅ primary"]
    end

    subgraph KB ["Knowledge Base  (src/infradx/knowledge/)"]
        Loader["loader.py\nKnowledgeBase.search()"]
        YAML["data/\nlinux.yaml  · 13건\naix.yaml    · 7건\nnetwork.yaml · 7건\ndisk.yaml   · 7건\nk8s.yaml    · 6건\nmonitoring.yaml · 3건\ncloud.yaml  · 8건"]
    end

    subgraph State ["Session State  (src/infradx/state/)"]
        Session["session.py\nSession\nPhase / Domain\nSystemSpec / Symptom\nHypothesis[]"]
    end

    User -->|입력| Chat
    Chat -->|텍스트 / 버튼 클릭| App
    App -->|stream_response| Core
    Core -->|스트리밍 청크| Chat
    Core -->|update_from_session| Sidebar
    Core -->|stream| Anthropic
    Core -->|stream| OpenAI
    Core -->|search| Loader
    Loader --> YAML
    Core -->|읽기/쓰기| Session
    App -->|읽기| Session
```

---

## Phase 상태머신

```mermaid
stateDiagram-v2
    direction LR

    [*] --> CLASSIFY : 세션 시작

    CLASSIFY --> GATHER_SPEC : 도메인 확정\n(server/network/disk/k8s/cloud)

    GATHER_SPEC --> DESCRIBE_SYMPTOM : 스펙 수집 완료\n(OS, 버전, 배포 유형 등)

    DESCRIBE_SYMPTOM --> REQUEST_METRICS : 증상 4개 항목 완료\n→ 초기 가설 자동 생성

    REQUEST_METRICS --> ANALYZE : 메트릭 결과 수신

    ANALYZE --> REQUEST_METRICS : 가설 미확정\n추가 메트릭 필요

    ANALYZE --> HYPOTHESIZE : 고신뢰도 가설 확정\n(HIGH confidence)

    HYPOTHESIZE --> REPRODUCE : 근본 원인 확정
    HYPOTHESIZE --> RECOMMEND : 근본 원인 확정

    REPRODUCE --> [*] : 완료
    RECOMMEND --> [*] : 완료

    note right of DESCRIBE_SYMPTOM
        초기 가설 목록 자동 출력
        1. [MED] ...
        2. [LOW] ...
    end note

    note right of ANALYZE
        가설 신뢰도 업데이트
        정상 범위 vs 관측값 비교
    end note
```

---

## 가설 Lifecycle

```mermaid
stateDiagram-v2
    direction LR

    [*] --> investigating : DESCRIBE_SYMPTOM 완료\n초기 가설 생성 시

    investigating --> investigating : ANALYZE 반복\n신뢰도(HIGH/MED/LOW) 업데이트\n근거 누적

    investigating --> validated : HYPOTHESIZE\n근본 원인과 일치 → ✅ 확정

    investigating --> invalidated : HYPOTHESIZE\n근본 원인과 불일치 → ❌ 기각

    validated --> [*]
    invalidated --> [*]
```

---

## 멀티 백엔드 구조

```mermaid
flowchart LR
    ENV["INFRADX_PROVIDER\n환경변수"]

    ENV -->|openai| OAI["_OpenAIBackend\nopenai.AsyncOpenAI\n모델: gpt-4o"]
    ENV -->|anthropic| ANT["_AnthropicBackend\nanthropics.Anthropic\n모델: claude-sonnet-4-6"]

    OAI --> API1["OpenAI API\nChat Completions\n(streaming)"]
    ANT --> API2["Anthropic API\nMessages\n(streaming)"]

    API1 --> Core["AgentCore\nstream_response()"]
    API2 --> Core
```

---

## 지식베이스 검색 흐름

```mermaid
flowchart TD
    Session["Session 상태\nerror_text\ntop_hypothesis\ncloud_provider\nk8s_distribution"]

    Session --> Query["쿼리 조합\n최대 200자"]

    Query --> Search["KnowledgeBase.search()\n키워드 TF-IDF 스코어링\ntitle ×3.0 / keywords ×2.5\nsymptoms ×2.0 / dmesg ×2.0\nroot_causes ×1.0"]

    Search --> Filter{"도메인 필터"}
    Filter -->|kubernetes / cloud| NoOSFilter["OS 필터 없음\n(_cross_os 처리)"]
    Filter -->|server / disk / network| OSFilter["OS 타입 필터 적용\nlinux / aix / other"]

    NoOSFilter --> Top2["상위 2개 항목 선택"]
    OSFilter --> Top2

    Top2 --> Inject["시스템 프롬프트에 주입\n[Knowledge Base — 관련 알려진 이슈:]"]
```

---

## 디렉터리 구조

```
infradx/
├── AGENT.md                    # 메인 에이전트 시스템 프롬프트 (8단계 상태머신)
├── CLAUDE.md                   # Claude Code 프로젝트 컨텍스트
├── codex/
│   └── agent_instructions.md  # OpenAI Codex / GPT-4 호환 지침 (Function Calling)
├── skills/                     # 단계별 스킬 파일 (AgentCore가 시스템 프롬프트에 병합)
│   ├── classify.md
│   ├── gather-context.md
│   ├── request-metrics.md
│   ├── analyze.md
│   ├── hypothesize.md
│   ├── reproduce.md
│   └── recommend.md
├── docs/
│   └── architecture.md        # 이 파일 — Mermaid 아키텍처 다이어그램
├── src/infradx/
│   ├── __main__.py             # 진입점 (.env 로드 → InfraDxApp 실행)
│   ├── agent/
│   │   └── core.py             # AgentCore: 스트리밍, KB 주입, 가설 파싱
│   ├── state/
│   │   └── session.py          # Phase · Session · Hypothesis · SystemSpec
│   ├── knowledge/
│   │   ├── loader.py           # KnowledgeBase: YAML 로드 + 키워드 검색
│   │   └── data/               # 도메인별 Known Issue DB (총 51개)
│   └── tui/
│       ├── app.py              # Textual 앱: 버튼 핸들러, Ctrl+C/N/S/Q
│       └── widgets/
│           ├── chat.py         # 대화 패널 + 액션 버튼 3개
│           └── sidebar.py      # 진행 단계 + 시스템 정보 + 가설 상태 배지
├── .env.example
└── pyproject.toml
```
