# Demo environment (AWS Fargate)

Stands up one tiny Fargate task that **continuously logs 503 / timeout / DB-pool
errors** and **burns CPU**, so the **Logs** and **Metrics** nodes have real data
to find. It's a single CloudFormation stack, so teardown is one command.

- Cluster `api-prod-cluster` · Service `api-prod` · Log group `/ecs/api-prod`
- Cost ≈ **$0.30/day** while running — delete it when done.

## 1. Deploy

Needs AWS CLI credentials that can create ECS/IAM/Logs resources and a **default
VPC** in the region (new accounts have one).

```bash
bash demo/deploy.sh                 # ap-southeast-1 by default
# or:  REGION=us-east-1 bash demo/deploy.sh
```

Wait ~3–5 min for the task to reach `RUNNING` and metrics to publish.

## 2. Point the copilot at it

In the web UI's **Configuration**: set **Region** `ap-southeast-1`, add an
**Anthropic key**, and either leave the AWS fields blank (uses your `~/.aws`
profile) or create a read-only key:

```bash
aws iam create-user --user-name copilot-readonly
aws iam put-user-policy --user-name copilot-readonly \
  --policy-name copilot-readonly \
  --policy-document file://demo/copilot-readonly-policy.json
aws iam create-access-key --user-name copilot-readonly
```

## 3. Investigate

Send in the chat bar:

> **ECS service api-prod in cluster api-prod-cluster returning 503s and high CPU for 20 minutes**

**Logs** is the deterministic signal — it finds the seeded errors every run.
**Metrics** shows CPU ~100% when the planner carries the cluster name into the
metrics thread (`AWS/ECS` metrics need both `ClusterName` and `ServiceName`),
which is why the incident names the cluster. Give metrics a few minutes to
populate.

## 4. Tear down

```bash
bash demo/teardown.sh   # removes the service, task, SG, IAM role, and log group
```
