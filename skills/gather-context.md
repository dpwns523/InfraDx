# Skill: gather-context

## Trigger
- `session.domain` is set
- `session.spec` is incomplete

## Input
- `session.domain`: server | network | disk

## Action
Ask for system specification fields **one group at a time** (not all at once).

---

### Domain: server

**Step 1** — Deployment type
```
서버 유형을 선택해 주세요:
  [1] 베어메탈 (물리 서버)
  [2] 가상머신 (VM)
  [3] 컨테이너 (Docker/K8s)
```

If VM → ask hypervisor: KVM / VMware ESXi / Microsoft Hyper-V / IBM LPAR / 기타

**Step 2** — OS
```
운영체제를 알려주세요 (명령어 결과 붙여넣기):

Linux:  uname -a
AIX:    oslevel -s && uname -a
Other:  직접 입력
```

Parse kernel version from output. Store:
- `spec.os_type`: linux | aix | windows | other
- `spec.kernel_version`: e.g., `5.15.0-91-generic`
- `spec.arch`: x86_64 | aarch64 | ppc64le

**Step 3** — Resources (Linux)
```
CPU/메모리 정보를 알려주세요:
  lscpu | grep -E "^CPU\(s\)|Model name|Architecture"
  free -h
```

---

### Domain: network

**Step 1** — Problem layer
```
문제가 발생하는 네트워크 계층을 선택해 주세요:
  [1] L2 — MAC, VLAN, spanning tree
  [2] L3 — IP 라우팅, 서브넷
  [3] L4 — TCP/UDP 포트, 방화벽
  [4] L7 — HTTP/HTTPS, DNS, 애플리케이션 프로토콜
  [5] 모름
```

**Step 2** — Endpoints
```
출발지 IP와 목적지 IP/호스트명을 알려주세요.
```

**Step 3** — Devices involved
```
관련 네트워크 장비를 알려주세요 (해당하는 것만):
- NIC 모델 및 드라이버
- 스위치/라우터 벤더 및 모델
- 방화벽/로드밸런서 (있는 경우)
```

---

### Domain: disk

**Step 1** — Disk type
```
스토리지 유형을 선택해 주세요:
  [1] 내장 디스크 (Internal) — 서버에 직접 장착
  [2] 외장 스토리지 — SAN / NAS / DAS
```

**Step 2** — Interface & media
```
인터페이스와 미디어 타입을 알려주세요:
  인터페이스: NVMe / SATA / SAS / FC / iSCSI
  미디어:     SSD / HDD / NVMe SSD
  RAID:       없음 / RAID 레벨 / 벤더 RAID 카드
```

**Step 3** — Current layout
```
현재 디스크 구성을 확인해 주세요:
  lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
  df -hT
```

---

## Output
- Populates `session.spec` object
- Transitions to `describe-symptom` (inline in AGENT.md Phase 3)

## Validation
- OS parse failure → ask user to paste raw output again
- Unknown vendor/model → store as-is, note for knowledge base lookup
