# Skill: classify

## Trigger
- Session start (no domain set)
- User describes an issue without specifying domain

## Input
- `session.domain` is null or unknown

## Action
Present a single-choice question:

```
어떤 환경/영역에서 문제가 발생했나요?

  [1] 서버      — OS, 프로세스, 메모리, CPU, 커널 패닉 (베어메탈 / VM)
  [2] 네트워크   — 연결 불가, 지연, 패킷 손실, 방화벽, BGP
  [3] 디스크     — I/O 오류, 파일시스템, RAID, SAN/NAS
  [4] Kubernetes — Pod 장애, 스케줄링, 네트워크 정책, RBAC, 스토리지
  [5] 퍼블릭 클라우드 — AWS / GCP / Azure / NCP 관리형 서비스 장애

번호 또는 키워드로 입력해 주세요.
```

## Mapping
| Input | domain |
|-------|--------|
| 1, 서버, server, linux, aix, bare metal, vm | `server` |
| 2, 네트워크, network, net | `network` |
| 3, 디스크, disk, storage, san, nas | `disk` |
| 4, k8s, kubernetes, kubectl, pod, 쿠버네티스 | `kubernetes` |
| 5, cloud, aws, gcp, azure, ncp, 클라우드, ec2, gke, aks, eks | `cloud` |
| 기타 키워드 | AI가 추론 후 확인 요청 |

## Output
- Sets `session.domain`
- Transitions to `gather-context` skill

## Edge Cases
- 복합 장애 (예: K8s 위에서 클라우드 디스크 이상): 가장 가까운 증상 레이어 선택 후 Notes에 기록
  - "EKS Pod I/O 오류" → kubernetes 선택, 클라우드 정보는 gather-context에서 추가 수집
  - "AWS RDS 연결 실패" → cloud 선택
- 모르겠음: "증상을 자유롭게 설명해 주시면 제가 분류해 드릴게요" 응답
