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
- **멀티 프로바이더** — Claude Code CLI(API 키 불필요), OpenAI GPT-4o, Anthropic Claude 선택 가능
- **재현 시나리오 생성** — 근본 원인 확정 후 최소 재현 절차와 격리 테스트 명령어 제공
- **명령어 클립보드 복사** — 제시된 진단 명령어를 `Ctrl+C`로 즉시 복사
- **컨텍스트 게이지** — 사이드바에서 현재 토큰 사용량을 실시간으로 확인

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
| `Shift+Enter` | 줄바꿈 (여러 줄 입력) |
| `Ctrl+C` | 마지막 제시 명령어 클립보드 복사 |
| `Ctrl+S` | 현재 세션을 마크다운 보고서로 저장 (`result/` 디렉토리) |
| `Ctrl+N` | 새 세션 시작 |
| `Ctrl+Q` | 종료 |

### 액션 버튼

채팅 입력창 위에 빠른 액션 버튼 3개가 있습니다.

| 버튼 | 동작 |
|------|------|
| `📊 메트릭 분석` | 현재 가설 기준으로 다음 수집 명령어 요청 |
| `🔍 가설 업데이트` | 수집된 데이터로 가설 신뢰도 재평가 |
| `📋 결론 도출` | 최종 진단과 권고사항 출력 |

### 사이드바

우측 사이드바에서 진행 상황을 한눈에 확인할 수 있습니다.

- **진행 단계** — 현재 단계(`→`) 및 완료 단계(`✓`) 표시. 클릭하면 해당 단계를 다시 수행합니다.
- **시스템 정보** — 수집된 OS, Cloud, K8s 스펙 요약
- **현재 가설** — AI가 추론 중인 가설 목록과 신뢰도/상태
- **컨텍스트 사용량** — 현재 요청의 토큰 수 / 모델 컨텍스트 한계 게이지

---

## 터미널에서 시작하는 방법

- [macOS / Linux](#macos--linux)
- [Windows](#windows)

---

### macOS / Linux

#### 1. 저장소 클론

```bash
git clone https://github.com/dpwns523/InfraDx.git
cd InfraDx
```

#### 2. Python 환경 설정

Python 3.11 이상이 필요합니다.

```bash
# uv 설치 (미설치 시)
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.local/bin/env   # 또는 터미널 재시작

uv python install 3.11
uv venv --python 3.11
source .venv/bin/activate
```

#### 3. 패키지 설치

```bash
uv pip install -e .

# OpenAI GPT-4o 함께 사용 시
uv pip install -e ".[openai]"
```

#### 4. 프로바이더 설정 및 실행

```bash
cp .env.example .env
# .env 편집 후
python -m infradx
```

---

### Windows

> **권장 환경:** Windows 10/11 + PowerShell 7 또는 Windows Terminal
> Claude Code CLI가 설치된 경우 API 키 없이 바로 사용할 수 있습니다.

#### 1. 저장소 클론

```powershell
git clone https://github.com/dpwns523/InfraDx.git
cd InfraDx
```

#### 2. Python 환경 설정

```powershell
# uv 설치 (미설치 시) — PowerShell에서 실행
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
# 터미널 재시작 후

uv python install 3.11
uv venv --python 3.11
.venv\Scripts\activate
```

#### 3. 패키지 설치

```powershell
uv pip install -e .

# OpenAI GPT-4o 함께 사용 시
uv pip install -e ".[openai]"
```

#### 4. 프로바이더 설정

```powershell
copy .env.example .env
notepad .env   # 또는 원하는 편집기로 열기
```

`.env` 파일 내용 예시:

```env
# Claude Code CLI 사용 (API 키 불필요, Pro 구독 활용) — 권장
INFRADX_PROVIDER=claudecode

# OpenAI GPT-4o 사용 시
# INFRADX_PROVIDER=openai
# OPENAI_API_KEY=sk-your-openai-key-here
# INFRADX_MODEL=gpt-4o

# Anthropic Claude API 사용 시
# INFRADX_PROVIDER=anthropic
# ANTHROPIC_API_KEY=sk-ant-your-key-here
# INFRADX_MODEL=claude-sonnet-4-6
```

#### 5. 한글 출력 설정 (Windows 전용)

터미널에서 한글이 깨지는 경우 실행 전 아래 명령어를 입력합니다.

```powershell
chcp 65001
$env:PYTHONUTF8 = "1"
```

매번 설정하지 않으려면 PowerShell 프로파일에 추가합니다.

```powershell
Add-Content $PROFILE "`n`$env:PYTHONUTF8 = '1'"
Add-Content $PROFILE "`nchcp 65001 | Out-Null"
```

#### 6. 실행

```powershell
python -m infradx
```

> **pyperclip 오류 시** (Ctrl+C 복사 기능): `pip install pyperclip` 후 재실행

---

## AI 프로바이더

InfraDx는 세 가지 백엔드를 지원합니다. `INFRADX_PROVIDER` 환경변수로 선택합니다.

| `INFRADX_PROVIDER` | API 키 | 설명 |
|--------------------|--------|------|
| `claudecode` (또는 `local`) | **불필요** | 로컬에 설치된 `claude` CLI를 서브프로세스로 호출. Claude Code Pro 구독으로 인증. |
| `openai` (또는 `codex`) | **필수** (`OPENAI_API_KEY`) | OpenAI API를 직접 호출. GPT-4o 기본. `codex`는 같은 백엔드의 별칭. |
| `anthropic` (또는 `claude`) | **필수** (`ANTHROPIC_API_KEY`) | Anthropic API를 직접 호출. claude-sonnet-4-6 기본. |

> **주의:** `INFRADX_PROVIDER=codex`는 OpenAI **API** 백엔드의 별칭입니다.
> OpenAI의 Codex CLI 도구(`codex` 명령어)와 다르며, `OPENAI_API_KEY`가 필요합니다.
> API 키 없이 사용하려면 `claudecode` 프로바이더를 사용하세요.

### 프로바이더별 사전 조건

**claudecode** (권장, API 키 불필요)
```bash
# Claude Code 설치 확인
claude --version

# 로그인 상태 확인
claude auth status
```

**openai**
```bash
uv pip install -e ".[openai]"
# .env에 OPENAI_API_KEY 설정
```

**anthropic**
```bash
# anthropic 패키지는 기본 의존성에 포함
# .env에 ANTHROPIC_API_KEY 설정
```

---

## 환경변수 전체 목록

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `INFRADX_PROVIDER` | `openai` | AI 프로바이더 (`claudecode` / `openai` / `anthropic`) |
| `OPENAI_API_KEY` | — | OpenAI API 키 (`openai`/`codex` 사용 시 필수) |
| `ANTHROPIC_API_KEY` | — | Anthropic API 키 (`anthropic`/`claude` 사용 시 필수) |
| `INFRADX_MODEL` | 프로바이더별 기본값 | 사용할 모델 ID (선택) |

> `INFRADX_PROVIDER`를 설정하지 않으면 `openai`가 기본값입니다.
> API 키 없이 바로 시작하려면 `.env`에 `INFRADX_PROVIDER=claudecode`를 설정하세요.

---

## 필요 패키지

### 런타임 의존성

| 패키지 | 버전 | 용도 |
|--------|------|------|
| `textual` | ≥0.80.0 | TUI 프레임워크 |
| `anthropic` | ≥0.40.0 | Anthropic API 클라이언트 |
| `pyyaml` | ≥6.0 | 지식베이스 YAML 파싱 |
| `rich` | ≥13.0.0 | 터미널 마크다운 렌더링 |
| `python-dotenv` | ≥1.0.0 | `.env` 파일 로드 |
| `pyperclip` | ≥1.9.0 | 클립보드 복사 |

### 선택적 의존성

| 패키지 | 설치 방법 | 용도 |
|--------|----------|------|
| `openai` | `pip install -e ".[openai]"` | OpenAI GPT-4o 백엔드 |

### 개발 의존성

```bash
uv pip install -e ".[dev]"
```

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
│   └── agent_instructions.md    # OpenAI GPT-4o 호환 지침 (Function Calling 포함)
├── result/                      # Ctrl+S 보고서 저장 위치 (.gitignore에 포함)
├── src/infradx/
│   ├── agent/core.py            # AI 에이전트 코어 (스트리밍, KB 컨텍스트 주입)
│   ├── state/session.py         # 8단계 Phase 열거형 + 세션 데이터클래스
│   ├── knowledge/
│   │   ├── loader.py            # YAML KB 로더 + 키워드 검색 엔진
│   │   └── data/                # 도메인별 Known Issue DB (총 51개 항목)
│   └── tui/
│       ├── app.py               # Textual 메인 앱
│       └── widgets/
│           ├── chat.py          # 좌측 대화 패널 (마크다운 렌더링, 스트리밍)
│           └── sidebar.py       # 우측 사이드바 (단계/스펙/가설/토큰 게이지)
├── .env.example                 # 환경변수 예시
└── pyproject.toml               # 패키지 메타데이터 및 의존성
```

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
