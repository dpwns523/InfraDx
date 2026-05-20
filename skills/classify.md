# Skill: classify

## Trigger
- Session start (no domain set)
- User describes an issue without specifying domain

## Input
- `session.domain` is null or unknown

## Action
Present a single-choice question:

```
어떤 영역에서 문제가 발생했나요?

  [1] 서버   — OS, 프로세스, 메모리, CPU, 커널 패닉
  [2] 네트워크 — 연결 불가, 지연, 패킷 손실, 방화벽
  [3] 디스크  — I/O 오류, 파일시스템, 스토리지 어레이

번호 또는 키워드로 입력해 주세요.
```

## Mapping
| Input | domain |
|-------|--------|
| 1, 서버, server | `server` |
| 2, 네트워크, network, net | `network` |
| 3, 디스크, disk, storage | `disk` |
| 기타 키워드 | AI가 추론 후 확인 요청 |

## Output
- Sets `session.domain`
- Transitions to `gather-context` skill

## Edge Cases
- 복합 장애 (예: 서버 디스크 동시 이상): 우선 순위 높은 것 하나 선택 후 나머지는 Notes에 기록
- 모르겠음: "증상을 설명해 주시면 제가 분류해 드릴게요" 응답
