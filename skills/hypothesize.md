# Skill: hypothesize

## Trigger
- Two or more metric cycles completed
- One hypothesis reaches HIGH confidence
- All alternative hypotheses eliminated

## Input
- `session.domain`
- `session.spec`
- `session.symptom`
- `session.metrics_collected`
- `session.hypotheses`

## Output Format

```markdown
## 최종 진단

**근본 원인:** <root cause — one clear sentence>

**신뢰도:** HIGH | MED | LOW

**근거:**
- <evidence 1> (출처: <metric name>)
- <evidence 2> (출처: <metric name>)
- <evidence 3> (출처: symptom description)

**기각된 가설:**
- <hypothesis A> — 기각 근거: <contradicting metric>
- <hypothesis B> — 기각 근거: <contradicting metric>

**불확실성:**
<any remaining unknowns or caveats>
```

---

## Common Root Cause Patterns

### Server — Linux

| Symptom Pattern | Root Cause | Key Evidence |
|----------------|-----------|--------------|
| High load + high %wa | Disk I/O bottleneck | iostat %util > 90, await spike |
| High load + low %wa | CPU saturation or lock contention | %us/%sy high, run queue > CPUs |
| OOM kills in dmesg | Memory exhaustion | free shows near-zero, swap used |
| Process crash + core dump | Application bug / segfault | dmesg `segfault`, coredump path |
| Gradual slowdown over hours | Memory leak | free shows steady decrease, no OOM yet |
| High CPU single process | Runaway thread / infinite loop | ps aux shows one pid at 100%+ |
| NFS hang / D state processes | Remote filesystem unresponsive | ps shows many processes in D state |
| Repeated kernel messages | Driver bug / hardware fault | dmesg shows repeated error pattern |

### Server — AIX

| Symptom Pattern | Root Cause | Key Evidence |
|----------------|-----------|--------------|
| topas shows high CPU/IO | paging space exhaustion | svmon shows high paging |
| errpt hardware errors | Disk/adapter hardware fault | errpt -a shows PERM errors |
| LPAR CPU throttling | Shared pool contention | topas shows entitled % exceeded |

### Network

| Symptom Pattern | Root Cause | Key Evidence |
|----------------|-----------|--------------|
| Intermittent loss to one hop | Upstream congestion or faulty link | mtr shows consistent loss at hop N |
| All connections to one host fail | Routing black hole or firewall rule | traceroute stops at specific hop |
| TCP retransmits spike | Network congestion or MTU mismatch | netstat -s retransmit rate high |
| NIC drops increasing | NIC ring buffer overflow | ethtool -S shows rx_missed_errors |
| High RTT variance | IRQ affinity or NIC interrupt issue | ethtool -S interrupts imbalanced |

### Disk

| Symptom Pattern | Root Cause | Key Evidence |
|----------------|-----------|--------------|
| I/O errors in dmesg | Failing disk / bad sectors | smartctl shows reallocated sectors |
| RAID degraded | Failed disk in array | cat /proc/mdstat shows [UU_] |
| Filesystem read-only remount | FS corruption detected | dmesg shows EXT4/XFS error + remount |
| High await, low %util | Storage array queue depth saturated | multipath shows path errors |
| iSCSI session drops | Network path failure or target overload | iscsiadm shows session recovery |

---

## Escalation Triggers
If after 5 metric cycles no HIGH-confidence hypothesis exists:
- State explicitly: "진단에 충분한 정보가 부족합니다"
- List what information would resolve ambiguity
- Suggest escalation path: vendor support, kernel debug, on-site inspection
