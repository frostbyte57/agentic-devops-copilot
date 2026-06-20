# Runbook: High CPU on ECS service

## Symptoms
- ECS service CPUUtilization sustained above 85-90%.
- Elevated request latency, intermittent 503/504 responses from the load balancer.
- Tasks being recycled by health checks.

## Likely causes
- A recent deploy introduced an inefficient code path (e.g. an N+1 database query,
  an unbounded loop, or newly added synchronous/blocking work per request).
- Traffic spike beyond provisioned task count.
- A dependency slowdown causing request pile-up and CPU spin.

## Investigation
1. Correlate the incident start time with the most recent deployment.
2. Inspect CloudWatch Logs for repeated slow-query or timeout signatures.
3. Compare CPU/memory before and after the deploy window.

## Remediation
- If a bad query was introduced: optimize it (add the missing index, batch the
  reads, use `.select_related()` / eager loading to kill N+1s) and ship a fix.
- As an immediate mitigation, scale the ECS service out (raise the desired task
  count) to absorb load while the fix is prepared.
- Consider a rollback to the previous task definition if the regression is severe.
