# Skill: request-metrics

## Trigger
- Hypothesis formed but not yet confirmed
- After receiving metrics, new hypothesis branches emerge

## Input
- `session.domain`
- `session.spec`
- `session.hypothesis` (current working hypothesis)
- `session.metrics_collected` (list of already-collected metrics)

## Constraint
**Request exactly ONE command block per turn.**
Never ask for multiple unrelated metrics at once.

## Output Format
```
현재 가설: `<hypothesis text>`

이를 확인/기각하기 위해 다음 명령어 결과를 붙여넣어 주세요:

```bash
<command>
```

결과에서 특히 `<specific field or pattern>`을 확인할 예정입니다.
```

---

## Metric Decision Tree

### server/linux — CPU/Load issue
```
Hypothesis: CPU saturation
→ top -bn1 | head -25

Hypothesis: I/O wait causing load spike
→ iostat -xz 1 5

Hypothesis: Memory pressure / swap
→ free -h && vmstat 1 5

Hypothesis: Kernel OOM or crash
→ dmesg -T | grep -iE "oom|killed|panic|call trace" | tail -30

Hypothesis: Runaway process
→ ps aux --sort=-%cpu | head -20
→ ps aux --sort=-%mem | head -20

Hypothesis: File descriptor exhaustion
→ lsof -n | wc -l && cat /proc/sys/fs/file-max

Hypothesis: Zombie process accumulation
→ ps aux | awk '$8=="Z"' | wc -l
```

### server/linux — Network from host
```
Hypothesis: TCP connection saturation
→ ss -s

Hypothesis: Network errors / drops
→ ip -s link show <iface>
→ ethtool -S <iface> | grep -iE "error|drop|miss"

Hypothesis: DNS resolution failure
→ dig +time=3 <hostname> && cat /etc/resolv.conf

Hypothesis: Firewall blocking
→ iptables -L -n -v | head -40
```

### server/linux — Disk I/O issue
```
Hypothesis: Disk I/O saturation
→ iostat -xz 1 5

Hypothesis: Hardware disk error
→ dmesg -T | grep -iE "error|reset|fault|timeout|i/o" | tail -30
→ smartctl -a /dev/<device>

Hypothesis: Filesystem full or inode exhaustion
→ df -hT && df -i

Hypothesis: Stuck I/O / hung process
→ dmesg -T | grep -i "task blocked"
→ ls /proc/*/wchan 2>/dev/null | xargs -I{} sh -c 'echo {} $(cat {})' | grep -v "0" | head -20
```

### server/aix
```
Hypothesis: CPU saturation
→ topas -P (10 seconds)

Hypothesis: Memory pressure
→ svmon -G && lsps -s

Hypothesis: Disk error
→ errpt -a | head -80

Hypothesis: Network issue
→ netstat -s | grep -iE "error|fail|retrans"
→ entstat -d <adapter> | grep -iE "error|drop"
```

### network
```
Hypothesis: Basic connectivity loss
→ ping -c 20 -i 0.2 <target>

Hypothesis: Routing issue
→ traceroute -n -w 2 <target>

Hypothesis: Packet loss at specific hop
→ mtr --report --report-cycles 20 <target>

Hypothesis: NIC hardware error
→ ethtool -S <iface>
→ ip -s link show <iface>

Hypothesis: TCP session issue
→ ss -tn state established | head -30
→ netstat -s | grep -iE "retransmit|reset|fail"

Hypothesis: Firewall/ACL dropping packets
→ tcpdump -i <iface> -c 50 host <target> -nn
```

### disk
```
Hypothesis: I/O saturation
→ iostat -xz 1 5

Hypothesis: SMART error / failing disk
→ smartctl -a /dev/<device>

Hypothesis: RAID degraded
→ cat /proc/mdstat
→ mdadm --detail /dev/<array>

Hypothesis: Filesystem corruption
→ dmesg -T | grep -iE "ext4|xfs|btrfs|error|corrupt" | tail -30

Hypothesis: SAN/iSCSI path issue
→ multipath -ll
→ iscsiadm -m session -P 3 | grep -iE "state|error"
```

---

## Skip Logic
If a metric was already collected (`session.metrics_collected`), do not request it again.
Instead, reference the previous result: "앞서 수집한 `iostat` 결과에서 `%util` 값이 98%였는데..."
