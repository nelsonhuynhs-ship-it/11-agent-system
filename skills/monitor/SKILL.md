---
name: ck:monitor
description: "Observability agent. Track agent performance metrics, execution times, success rates. Alert on issues."
argument-hint: "[metrics to check or 'start monitoring']"
metadata:
  author: nelson-freight
  version: "1.0.0"
---

# Monitor Agent

Agent theo doi performance va health cua 11-agent workflow. Track metrics, log execution, alert khi co van de.

## KHI NAO DUNG

- Muon biet agents chay the nao
- Sau khi run autonomous pipeline
- Periodic health check
- Debugging performance issues

## TRACKED METRICS

| Metric | Description |
|--------|-------------|
| Execution time | Thoi gian moi phase/agent |
| Success rate | % tasks completed vs failed |
| Token usage | Tokens consumed per agent |
| Error rate | So loi / total runs |
| Escalation count | Lan phai hoi user |
| Loop count | So iterations truoc khi done |

## METRICS STORAGE

Metrics luu tai:
~/.claude/metrics/
  daily/YYYY-MM-DD.json
  weekly/YYYY-WNN.json
  monthly/YYYY-MM.json

## COMMANDS

/ck:monitor start - Bat dau tracking
/ck:monitor report [period] - Xem report (today/week/month)
/ck:monitor health - Kiem tra health cua tat ca agents
/ck:monitor alert - Xem recent alerts

## ALERT RULES

| Condition | Severity | Action |
|-----------|----------|--------|
| Error rate >20% | WARNING | Log + continue |
| Token usage spike >2x | WARNING | Log + notify |
| Agent timeout >5min | CRITICAL | Alert user |
| 3x escalation | CRITICAL | Alert user |
| Success rate <60% | WARNING | Log + recommend review |

## OUTPUT FORMAT

Monitor Report:
  design-finder: 2 runs, 100% success, avg 45s
  code-reviewer: 5 runs, 80% success, avg 2m
  Health: GREEN
