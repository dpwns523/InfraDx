# Skill: reproduce

## Trigger
- Root cause confirmed (HIGH confidence hypothesis)
- User requests reproduction scenario

## Input
- `session.spec`
- `session.symptom`
- `session.root_cause`
- `session.metrics_collected`

## Output Format

```markdown
## 재현 시나리오

### 환경 조건
- **OS / 커널:** <os_type> <kernel_version>
- **하드웨어:** <bare metal|VM — hypervisor>
- **관련 설정:** <config files, parameters, versions>
- **선행 조건:** <what must be true before reproducing>

### 재현 절차
1. <step 1>
2. <step 2>
3. <step 3>
...

### 격리 테스트 (Isolation Test)
가장 빠르게 재현을 확인하는 최소 명령어:

```bash
<minimal reproduction command>
```

예상 출력 (이상 증상 발생 시):
```
<expected error output>
```

### 예상 결과 (정상)
<what should happen if the system is healthy>

### 실제 결과 (이상 증상)
<what actually happens — based on user-reported symptoms>

### 재현 성공 기준
<how to know the reproduction succeeded>
```

---

## Scenario Templates by Root Cause

### CPU Saturation (Runaway Process)
```markdown
### 재현 절차
1. 프로세스 PID 확인: `ps aux --sort=-%cpu | head -5`
2. 해당 프로세스 스택 덤프: `pstack <pid>` 또는 `gdb -p <pid> -batch -ex bt`
3. strace로 시스템 콜 추적: `strace -p <pid> -c -f 2>&1 | head -30`

### 격리 테스트
```bash
# CPU 부하 시뮬레이션 (테스트 환경에서만)
stress-ng --cpu $(nproc) --timeout 30s --metrics-brief
```
```

### Memory Leak Reproduction
```markdown
### 재현 절차
1. 메모리 베이스라인 측정: `free -h && date`
2. 문제 서비스 재시작 후 모니터링:
   `watch -n 5 'ps -o pid,vsz,rss,comm -p <pid>'`
3. 30분 간격으로 free -h 반복 측정

### 격리 테스트
```bash
# 메모리 증가 추이 확인 (5초 간격 10회)
for i in $(seq 10); do
  echo "=== $(date) ===" && free -m | grep Mem
  sleep 5
done
```
```

### Disk I/O Saturation
```markdown
### 재현 절차
1. 현재 I/O 부하 프로세스 확인: `iotop -b -n 3 | head -20`
2. I/O 포화 재현 (테스트 환경):
   `dd if=/dev/urandom of=/tmp/test bs=4k count=100000 oflag=dsync`
3. 동시에 iostat으로 모니터링: `iostat -xz 1`

### 격리 테스트
```bash
iostat -xz 1 10 | grep -E "Device|sd|nvme" | grep -v "^$"
```
```

### Network Packet Loss
```markdown
### 재현 절차
1. 기본 연결성 확인: `ping -c 100 <target_ip>`
2. 경로 추적: `mtr --report --report-cycles 30 <target_ip>`
3. 특정 시간대 트래픽 캡처:
   `tcpdump -i <iface> -w /tmp/capture_$(date +%Y%m%d_%H%M%S).pcap host <target_ip>`

### 격리 테스트
```bash
# 패킷 손실율 측정 (1분간)
ping -c 60 -i 1 <target_ip> | tail -3
```
```

### RAID Degraded
```markdown
### 재현 절차
1. RAID 상태 확인: `cat /proc/mdstat`
2. 배열 상세 정보: `mdadm --detail /dev/md0`
3. 실패 디스크 SMART 확인: `smartctl -a /dev/<failed_disk>`

### 격리 테스트
```bash
cat /proc/mdstat && echo "---" && lsblk | grep -E "md|disk"
```
```

---

## Rules
- Reproduction commands that are destructive must be clearly marked: `⚠️ 테스트 환경에서만 실행`
- If reproduction requires vendor-specific tooling, note it as prerequisite
- Always include the isolation test — the single fastest verification command
