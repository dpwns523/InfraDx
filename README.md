# InfraDx

> AI 기반 인프라 트러블슈팅 도구 — 단계별 추론으로 근본 원인을 찾아드립니다.

```
╔══════════════════════════════════════════════════════╗
║  InfraDx  —  AI Infrastructure Diagnostics          ║
╠══════════════════════════════════════════════════════╣
║  You: 서버가 갑자기 느려졌어요                            ║
║                                                      ║
║  InfraDx: 어떤 환경에서 발생했나요?                        ║
║    [1] 서버  [2] 네트워크  [3] 디스크                     ║
║    [4] Kubernetes  [5] 퍼블릭 클라우드                    ║
╚══════════════════════════════════════════════════════╝
```

---

## 소개

**InfraDx**는 서버 운영자, DevOps 엔지니어, SRE를 위한 AI 트러블슈팅 도구입니다.
문제 증상을 입력하면 AI가 단계별로 추론하며 필요한 메트릭을 요청하고, 근본 원인과 재현 시나리오, 권고사항을 제시합니다.

### 주요 특징

- **단계별 추론** — 한 번에 하나씩 물어보며 가설을 검증합니다 (정보 폭탄 없음)
- **5개 도메인** — 서버(Linux/AIX), 네트워크, 디스크, Kubernetes, 퍼블릭 클라우드 (AWS/GCP/Azure)
- **지식베이스 연동** — 51개 Known Issue DB가 자동으로 관련 항목을 컨텍스트에 주입
- **멀티 프로바이더** — Anthropic Claude 또는 OpenAI GPT-4 선택 가능
- **재현 시나리오 생성** — 근본 원인 확정 후 최소 재현 절차와 격리 테스트 명령어 제공
- **명령어 클립보드 복사** — 제시된 진단 명령어를 `Ctrl+C`로 즉시 복사

---

## 지원 도메인

| 도메인 | 대상 환경 | 지식베이스 항목 |
|--------|---------|----------------|
| 서버 (Linux) | Ubuntu, RHEL, CentOS, Debian | 13개 |
| 서버 (AIX) | AIX 6.1 ~ 7.3, LPAR | 7개 |
| 네트워크 | L2~L7, BGP, DNS, 방화벽 | 7개 |
| 디스크 | HDD/SSD, RAID, SAN/iSCSI, NVMe | 7개 |
| Kubernetes | EKS, GKE, AKS, self-managed | 6개 |
| 모니터링 | Prometheus, AlertManager, Grafana | 3개 |
| 퍼블릭 클라우드 | AWS, GCP, Azure | 8개 |

---

## 트러블슈팅 플로우차트

```
사용자 입력 (증상 설명)
        │
        ▼
┌──────────────────┐
│   CLASSIFY       │  어떤 도메인? (서버/네트워크/디스크/K8s/클라우드)
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│   GATHER_SPEC    │  시스템 스펙 수집
│                  │  ├─ 서버: OS, 커널, 베어메탈/VM
│                  │  ├─ K8s: 배포 유형, 버전, 문제 범위
│                  │  └─ Cloud: 프로바이더, 서비스, 리전
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ DESCRIBE_SYMPTOM │  언제부터? 재현율? 에러 메시지? 최근 변경사항?
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ REQUEST_METRICS  │◄─────────────────────┐
│                  │  현재 가설 기반으로    │
│                  │  명령어 1개씩 요청    │
└────────┬─────────┘                      │
         │                               │
         ▼                               │
┌──────────────────┐                     │
│    ANALYZE       │  메트릭 파싱 +       │
│                  │  가설 신뢰도 업데이트 │
└────────┬─────────┘                     │
         │                               │
         ├── 가설 미확정 ────────────────►┘
         │
         ▼ (HIGH 신뢰도 가설 확정)
┌──────────────────┐
│   HYPOTHESIZE    │  근본 원인 확정 + 증거 요약
└────────┬─────────┘
         │
         ├──────────────────┐
         ▼                  ▼
┌──────────────┐   ┌──────────────────┐
│  REPRODUCE   │   │   RECOMMEND      │
│ 재현 시나리오 │   │  즉각조치 / 수정  │
│ 격리 테스트  │   │  / 예방 모니터링  │
└──────────────┘   └──────────────────┘
```

---

## 사용 방법

### 1. 증상 설명으로 시작

자유롭게 증상을 입력하거나, AI가 제시하는 선택지에서 선택합니다.

```
You: 새벽 3시부터 서버 응답이 느린데 CPU는 정상이에요
```

### 2. 도메인 분류

```
InfraDx: 어떤 환경/영역에서 문제가 발생했나요?
  [1] 서버  [2] 네트워크  [3] 디스크  [4] Kubernetes  [5] 퍼블릭 클라우드
```

### 3. 시스템 스펙 수집

```
InfraDx: OS 정보를 알려주세요.
         uname -a

You: Linux prod-01 5.15.0-91-generic #101-Ubuntu SMP ...
```

### 4. 단계별 메트릭 요청

AI가 현재 가설을 밝히고 필요한 명령어를 하나씩 요청합니다.

```
InfraDx: 현재 가설: `새벽 cron 작업으로 인한 I/O wait 증가`
         확인하기 위해 다음 명령어 결과를 붙여넣어 주세요:

         $ iostat -xz 1 5
```

결과를 붙여넣으면 AI가 분석하고 가설을 업데이트합니다.

### 5. 진단 결과 수신

```
InfraDx: ## 최종 진단

근본 원인: rsync 백업 작업이 기본 I/O 우선순위로 실행되어
          프로덕션 서비스와 디스크 I/O를 경합
신뢰도: HIGH

## 즉각 조치
ionice -c 3 -p <rsync_pid>

## 근본 원인 수정
ionice -c 3 nice -n 10 /usr/local/bin/backup.sh
```

### 키보드 단축키

| 단축키 | 기능 |
|--------|------|
| `Enter` | 메시지 전송 |
| `Ctrl+C` | 마지막 제시 명령어 클립보드 복사 |
| `Ctrl+S` | 현재 세션을 마크다운 보고서로 저장 (Desktop) |
| `Ctrl+N` | 새 세션 시작 |
| `Ctrl+Q` | 종료 |

### 액션 버튼

채팅 입력창 위에 빠른 액션 버튼 3개가 있습니다.

| 버튼 | 동작 |
|------|------|
| `📊 메트릭 분석` | 현재 가설 기준으로 다음 수집 명령어 요청 |
| `🔍 가설 업데이트` | 수집된 데이터로 가설 신뢰도 재평가 |
| `📋 결론 도출` | 최종 진단과 권고사항 출력 |

---

## 터미널에서 시작하는 방법

### 1. 저장소 클론

```bash
git clone https://github.com/<your-org>/infradx.git
cd infradx
```

### 2. Python 환경 설정

Python 3.11 이상이 필요합니다. `uv`를 사용하면 자동으로 설치됩니다.

```bash
# uv 설치 (미설치 시)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env   # 또는 터미널 재시작

# Python 3.11 설치 및 가상환경 생성
uv python install 3.11
uv venv --python 3.11
source .venv/bin/activate
```

### 3. 패키지 설치

```bash
# 기본 설치 (Anthropic Claude 사용)
uv pip install -e .

# OpenAI GPT-4 함께 사용 시
uv pip install -e ".[openai]"
```

### 4. API 키 설정

```bash
cp .env.example .env
```

`.env` 파일을 열고 사용할 프로바이더의 API 키를 입력합니다.

```env
# OpenAI GPT-4o / Codex 사용 시 (기본값)
INFRADX_PROVIDER=openai
OPENAI_API_KEY=sk-your-openai-key-here
INFRADX_MODEL=gpt-4o

# Anthropic Claude 사용 시
# INFRADX_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# INFRADX_MODEL=claude-sonnet-4-6
```

> **OpenAI API 키 발급:** [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
>
> **Anthropic API 키 발급:** [console.anthropic.com](https://console.anthropic.com)
> (Claude Code Pro 구독과 별개입니다)

### 5. 실행

```bash
python -m infradx
```

---

## 필요 패키지

### 런타임 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `anthropic` | ≥0.40.0 | Claude API 클라이언트 |
| `textual` | ≥0.80.0 | TUI 프레임워크 |
| `pyyaml` | ≥6.0 | 지식베이스 YAML 파싱 |
| `pydantic` | ≥2.0.0 | 데이터 모델 검증 |
| `python-dotenv` | ≥1.0.0 | `.env` 파일 로드 |
| `rich` | ≥13.0.0 | 터미널 텍스트 렌더링 |
| `pyperclip` | ≥1.9.0 | 클립보드 복사 |
| `aiosqlite` | ≥0.20.0 | 비동기 세션 저장 |
| `aiofiles` | ≥24.1.0 | 비동기 파일 I/O |

### 선택적 의존성

| 패키지 | 설치 방법 | 용도 |
|--------|----------|------|
| `openai` | `pip install -e ".[openai]"` | GPT-4/Codex 백엔드 |

### 개발 의존성

```bash
uv pip install -e ".[dev]"
```

| 패키지 | 용도 |
|--------|------|
| `pytest` | 테스트 |
| `pytest-asyncio` | 비동기 테스트 |
| `pytest-textual-snapshot` | TUI 스냅샷 테스트 |

---

## 프로젝트 구조

```
infradx/
├── AGENT.md                     # AI 에이전트 시스템 프롬프트 & 8단계 상태 머신
├── CLAUDE.md                    # Claude Code 프로젝트 컨텍스트
├── docs/
│   └── architecture.md          # 시스템 아키텍처 Mermaid 다이어그램
├── skills/                      # 모듈화된 스킬 파일 (AI가 각 단계에서 참조)
│   ├── classify.md              # 도메인 분류
│   ├── gather-context.md        # 시스템 스펙 수집
│   ├── request-metrics.md       # 가설별 명령어 결정 트리
│   ├── analyze.md               # 메트릭 분석 + 정상 범위 기준표
│   ├── hypothesize.md           # 패턴별 근본 원인 매핑
│   ├── reproduce.md             # 재현 시나리오 템플릿
│   └── recommend.md             # 즉각조치/근본수정/예방 템플릿
├── codex/
│   └── agent_instructions.md    # OpenAI Codex/GPT-4 호환 지침 (Function Calling 포함)
├── src/infradx/
│   ├── agent/core.py            # AI 에이전트 코어 (스트리밍, KB 컨텍스트 주입)
│   ├── state/session.py         # 8단계 Phase 열거형 + 세션 데이터클래스
│   ├── knowledge/
│   │   ├── loader.py            # YAML KB 로더 + 키워드 검색 엔진
│   │   └── data/                # 도메인별 Known Issue DB (총 51개 항목)
│   │       ├── linux.yaml       # Linux 서버 이슈 (13개)
│   │       ├── aix.yaml         # AIX 서버 이슈 (7개)
│   │       ├── network.yaml     # 네트워크 이슈 (7개)
│   │       ├── disk.yaml        # 디스크/스토리지 이슈 (7개)
│   │       ├── kubernetes.yaml  # Kubernetes 이슈 (6개)
│   │       ├── monitoring.yaml  # 모니터링 이슈 (3개)
│   │       └── cloud.yaml       # 퍼블릭 클라우드 이슈 (8개)
│   └── tui/
│       ├── app.py               # Textual 메인 앱
│       └── widgets/
│           ├── chat.py          # 좌측 대화 패널
│           └── sidebar.py       # 우측 사이드바 (단계/스펙/가설 표시)
├── .env.example                 # 환경변수 예시
└── pyproject.toml               # 패키지 메타데이터 및 의존성
```

---

## 환경변수 전체 목록

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `INFRADX_PROVIDER` | `openai` | AI 프로바이더 (`openai` / `anthropic`) |
| `OPENAI_API_KEY` | — | OpenAI API 키 (GPT-4o / Codex 사용 시 필수) |
| `ANTHROPIC_API_KEY` | — | Anthropic API 키 (Claude 사용 시 필수) |
| `INFRADX_MODEL` | `gpt-4o` | 사용할 모델 ID |
| `INFRADX_DB_PATH` | `~/.local/share/infradx/sessions.db` | 세션 저장 경로 |

---

## 지식베이스 확장

`src/infradx/knowledge/data/` 에 YAML 파일을 추가하면 자동으로 로드됩니다.

```yaml
# my-custom.yaml
domain: server
os: linux

issues:
  - id: custom-001
    title: 나만의 Known Issue
    severity: high           # critical / high / medium / low
    category: custom
    keywords: [키워드1, 키워드2]
    symptoms:
      - 증상 설명
    diagnosis_commands:
      - cmd: "진단 명령어"
        purpose: 명령어 목적
    root_causes:
      - 원인 설명
    fix:
      immediate:
        - 즉각 조치
      permanent:
        - 영구 수정
    prevention:
      - 예방 방법
```

---

## 라이선스

MIT License
