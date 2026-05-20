# Skill: analyze

## Trigger
- User pastes metric output

## Input
- `session.domain`
- `session.spec`
- `session.symptom`
- `metric_output`: raw text pasted by user
- `session.hypothesis`: current hypothesis list

## Output Format

```markdown
## 분석 결과

**수집된 지표 요약:**
| 지표 | 관측값 | 정상 범위 | 상태 |
|------|--------|-----------|------|
| <metric_name> | <value> | <normal> | 🔴 이상 / 🟡 경고 / 🟢 정상 |

**가설 업데이트 (신뢰도 순):**
1. [HIGH] <hypothesis> — 근거: <evidence from this metric>
2. [MED]  <hypothesis> — 근거: <evidence>
3. [LOW]  <hypothesis> — 근거: <evidence>

**제거된 가설:**
- <hypothesis> — 이유: <contradicting evidence>

**다음 단계:**
<one of:>
- 추가 메트릭 요청: `<metric name>`으로 가설 1을 확인합니다
- 가설 확정: 충분한 증거가 수집되었습니다 → 재현 시나리오 작성으로 이동
- 정보 부족: <what's missing and why>
```

---

## Normal Ranges Reference

### Linux CPU
| Metric | Warning | Critical |
|--------|---------|----------|
| load average / CPU count | > 0.7 | > 1.0 |
| %wa (iowait) | > 10% | > 30% |
| %us + %sy | > 80% | > 95% |

### Linux Memory
| Metric | Warning | Critical |
|--------|---------|----------|
| used / total | > 80% | > 95% |
| swap used | > 0 | > 20% total |
| dirty pages | > 500MB | > 2GB |

### Disk I/O (iostat)
| Metric | Warning | Critical |
|--------|---------|----------|
| %util | > 70% | > 90% |
| await (ms) | > 20ms (HDD) / > 5ms (SSD) | > 100ms |
| r/s + w/s | context-dependent | — |

### Network
| Metric | Warning | Critical |
|--------|---------|----------|
| packet loss (ping) | > 0.1% | > 1% |
| RTT jitter | > 5ms | > 20ms |
| TCP retransmit rate | > 0.01% | > 0.1% |
| NIC errors/drops | > 0 | increasing trend |

---

## Parsing Hints

### top / vmstat
- Look for `wa` column > 10 → I/O wait
- `si`/`so` > 0 → swap activity (memory pressure)
- `r` (run queue) > CPU count → CPU saturation

### iostat -x
- `%util` → disk busy percentage
- `await` → average I/O response time
- `svctm` (if present) → service time (< await means queuing)

### dmesg patterns
- `Out of memory: Kill process` → OOM killer
- `EXT4-fs error` / `XFS: internal error` → filesystem corruption
- `ata\d+: SATA link down` → disk disconnection
- `SCSI error` / `Medium Error` → disk hardware failure
- `Call Trace` → kernel panic / bug

### ss -s
- `estab` count growing unbounded → connection leak
- `timewait` > 10000 → TIME_WAIT exhaustion (need SO_REUSEADDR or tw_reuse)

---

## Rules
- Never invent values. Only analyze what was actually pasted.
- If output is truncated or garbled, ask for the full output.
- If the metric doesn't match any known pattern, state uncertainty explicitly.
