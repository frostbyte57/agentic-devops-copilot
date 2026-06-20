# Runbook: 5xx / 503 spike behind the load balancer

## Symptoms
- Sudden rise in 503/504 responses from the ALB/target group.
- Healthy host count dropping or flapping.
- Upstream timeouts in application logs.

## Likely causes
- Backend (ECS tasks) saturated — CPU/memory exhaustion or connection-pool
  exhaustion — so the load balancer has no healthy targets to route to.
- A deploy that increased per-request work or broke a downstream dependency.
- Database or cache outage causing requests to hang until timeout.

## Investigation
1. Check target group healthy host count and ECS task CPU/memory.
2. Pull the last 500 error log lines and look for the dominant exception.
3. Diff the most recent deploy for new blocking calls or query regressions.

## Remediation
- Restore healthy capacity: fix the resource exhaustion (optimize the hot path)
  and scale out tasks to recover the target group.
- Roll back the offending deploy if a regression is confirmed.
- Add/adjust timeouts and circuit breakers on the failing dependency.
