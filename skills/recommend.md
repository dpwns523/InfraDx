# Skill: recommend

## Trigger
- Root cause confirmed
- Reproduction scenario complete (or not needed)

## Input
- `session.root_cause`
- `session.spec`
- `session.symptom`

## Output Format

```markdown
## 권고사항

### 즉각 조치 (Immediate Mitigation)
> 지금 당장 증상을 완화할 수 있는 조치 — 근본 원인을 고치지 않아도 됨

- <action 1>
  ```bash
  <command if applicable>
  ```
- <action 2>

**예상 효과:** <what this achieves>
**주의사항:** <risks or side effects>

---

### 근본 원인 수정 (Root Cause Fix)
> 재발 방지를 위한 영구적 수정

- <fix 1 with context>
  ```bash
  <command or config change>
  ```
- <fix 2>

**검증 방법:**
```bash
<command to verify fix worked>
```

---

### 예방 및 모니터링 (Prevention)
> 동일 장애가 조기에 감지되도록 하는 알림/설정

**모니터링 추가:**
- <metric to monitor> — 임계값: <threshold>
  ```bash
  # 예시: Prometheus alerting rule 또는 cron-based check
  <example>
  ```

**설정 강화 (Hardening):**
- <config recommendation>
```

---

## Fix Templates by Root Cause

### OOM (Out of Memory)
```markdown
### 즉각 조치
- OOM으로 종료된 프로세스 재시작
- 메모리 많이 쓰는 프로세스 재시작 또는 종료:
  ```bash
  ps aux --sort=-%mem | head -5
  kill -9 <pid>
  ```

### 근본 원인 수정
- 메모리 누수 코드 수정 (application level)
- JVM이라면 heap 설정 조정: `-Xmx` 파라미터 검토
- 캐시 크기 제한 설정 (예: Redis maxmemory)
- 서버 메모리 증설 검토

### 모니터링 추가
- `MemAvailable` < 총 RAM의 10% → alert
  ```bash
  # cron every minute
  awk '/MemAvailable/{if($2 < THRESHOLD) print "LOW MEM: "$2"kB"}' /proc/meminfo
  ```
```

### Disk I/O Saturation
```markdown
### 즉각 조치
- I/O 폭주 프로세스 확인 및 제한:
  ```bash
  iotop -b -n 1 | head -10
  ionice -c 3 -p <pid>   # idle I/O class로 변경
  ```

### 근본 원인 수정
- I/O 스케줄러 변경 (SSD):
  ```bash
  echo "none" > /sys/block/sda/queue/scheduler
  ```
- 디스크 캐시 설정 최적화 (`vm.dirty_ratio`, `vm.dirty_background_ratio`)
- 고부하 워크로드를 별도 디스크/LUN으로 분리

### 모니터링 추가
- iostat %util > 80% 시 alert
```

### Network Packet Loss
```markdown
### 즉각 조치
- 해당 네트워크 경로 우회 라우팅 (가능한 경우)
- NIC 재초기화:
  ```bash
  ip link set <iface> down && sleep 1 && ip link set <iface> up
  ```

### 근본 원인 수정
- NIC 드라이버 업데이트
- 스위치 포트 재협상:
  ```bash
  ethtool -s <iface> speed 1000 duplex full autoneg off
  ```
- 케이블/SFP 교체 (물리적 이상인 경우)
- MTU 불일치 수정:
  ```bash
  ip link set <iface> mtu 1500
  ```

### 모니터링 추가
- ping loss > 0.5% → alert
- `ip -s link show` errors/dropped 증가율 모니터링
```

### Failing Disk (SMART error)
```markdown
### 즉각 조치
- 즉시 전체 데이터 백업 실행
- RAID라면 핫스페어 준비:
  ```bash
  mdadm /dev/md0 --add /dev/sdX   # 핫스페어 추가
  ```

### 근본 원인 수정
- 해당 디스크 교체 (RMA 또는 구매)
- 교체 후 RAID 재구성 완료 확인:
  ```bash
  watch cat /proc/mdstat
  ```

### 모니터링 추가
- smartctl -H 주간 cron + 결과 메일 알림
- RAID 상태 변경 시 mdadm --monitor 알림
```

---

## Rules
- 즉각 조치는 서비스 중단 없이 실행 가능한 것만 포함
- 재시작 또는 서비스 영향이 있는 조치는 명확히 표시: `⚠️ 서비스 중단 가능`
- 모니터링 예시는 기존 스택(Prometheus/Grafana/Nagios/기타)에 무관하게 범용적으로 작성
