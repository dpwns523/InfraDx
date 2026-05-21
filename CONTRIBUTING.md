# Contributing to InfraDx

## 로컬 개발 환경

```bash
git clone https://github.com/<your-org>/infradx.git
cd infradx

uv venv --python 3.11
source .venv/bin/activate
uv pip install -e ".[dev,openai]"

cp .env.example .env
# .env에 OPENAI_API_KEY 입력

python -m infradx
```

---

## 지식베이스(KB) 항목 추가

`src/infradx/knowledge/data/` 의 YAML 파일에 issue를 추가하거나 새 파일을 만들면 자동 로드됩니다.

### YAML 스키마

```yaml
domain: server          # server | network | disk | kubernetes | cloud | monitoring
os: linux               # linux | aix | kubernetes | cloud | monitoring | null (도메인 전체 적용)

issues:
  - id: linux-xxx-001                  # 도메인-카테고리-번호 형식
    title: 이슈 제목
    severity: high                     # critical | high | medium | low
    category: memory                   # 자유 형식 카테고리
    keywords: [키워드1, 키워드2]         # 검색 시 ×2.5 가중치
    symptoms:
      - 증상 설명 1
      - 증상 설명 2
    dmesg_patterns:                    # (선택) Linux dmesg 로그 패턴
      - "Out of memory"
    errpt_patterns:                    # (선택) AIX errpt 로그 패턴
      - "PERM DISK"
    diagnosis_commands:
      - cmd: "free -h"
        purpose: 메모리 사용량 확인
    root_causes:
      - 원인 설명
    fix:
      immediate:
        - 즉각 조치 명령어 또는 설명
      permanent:
        - 영구 수정 방법
    prevention:
      - 예방 방법 또는 모니터링 알림
    diagnosis_hints:                   # (선택) AI에게 주입되는 진단 힌트
      - "sar -r 1 5로 메모리 추세 확인"
```

### 주의사항

- `keywords` 값에 정수가 포함되면 따옴표로 감싸야 합니다: `"502"`, `"137"`
- YAML 값 안에 콜론(`:`)이 있으면 전체를 따옴표로 감쌉니다
- 추가 후 `python -c "from infradx.knowledge import get_knowledge_base; kb = get_knowledge_base(); print(kb.entry_count)"` 로 로드 확인

---

## 스킬 파일 추가

`skills/` 디렉터리에 `.md` 파일을 추가하면 AgentCore가 시스템 프롬프트에 자동 병합합니다.

```
skills/my-skill.md
```

파일명이 알파벳 순으로 정렬되어 프롬프트에 삽입됩니다. 기존 단계(phase)와 충돌하지 않도록 AGENT.md의 Skill Index 표를 함께 업데이트하세요.

---

## 백엔드 추가

`src/infradx/agent/core.py` 의 `_Backend` Protocol을 구현합니다.

```python
class _MyBackend:
    async def stream(self, system: str, messages: list[dict]) -> AsyncIterator[str]:
        ...
```

`_PROVIDERS` 딕셔너리에 키를 추가하면 `INFRADX_PROVIDER=mybackend` 로 선택 가능합니다.

---

## 테스트

```bash
pytest tests/ -v
```

현재 테스트는 KB 로더와 가설 파싱에 집중되어 있습니다. TUI 변경 시 `pytest-textual-snapshot` 을 활용하세요.

---

## PR 규칙

- KB 항목 추가: `kb: add <domain> issues` 형식의 커밋 메시지
- 스킬 추가: `skill: add <name>` 형식
- 버그 수정: `fix: <설명>`
- 기능 추가: `feat: <설명>`
