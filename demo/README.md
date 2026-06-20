# Copilot demo environment (AWS Fargate, via CloudFormation)

Stands up the smallest realistic thing for the copilot to investigate: one tiny
Fargate task that **continuously logs 503 / timeout / DB-pool errors** and
**burns CPU**, so both the **CloudWatch Logs** and **Metrics** nodes have real
data. Everything is one CloudFormation stack, so teardown is a single command.

- Cluster: `api-prod-cluster`  ·  Service: `api-prod`  ·  Log group: `/ecs/api-prod`
- Cost: ~0.25 vCPU / 0.5 GB Fargate ≈ **$0.30/day** while running. Delete it when done.

## 1. Deploy

You need AWS CLI configured with credentials that can create ECS/IAM/Logs
resources, and a **default VPC** in the region (new accounts have one).

```bash
bash demo/deploy.sh                 # region ap-southeast-1 by default
# or:  REGION=us-east-1 bash demo/deploy.sh
```

Wait ~3–5 minutes for the task to reach `RUNNING` and for `AWS/ECS` metrics to
start publishing.

## 2. Point the copilot at it

In the web UI's **Configuration**:

- **Region:** `ap-southeast-1`
- **Anthropic key** (and pick a model) — needed for the planner/summaries.
- **AWS Access key ID / Secret:** create a read-only key and attach
  [`copilot-readonly-policy.json`](./copilot-readonly-policy.json), e.g.

  ```bash
  aws iam create-user --user-name copilot-readonly
  aws iam put-user-policy --user-name copilot-readonly \
    --policy-name copilot-readonly \
    --policy-document file://demo/copilot-readonly-policy.json
  aws iam create-access-key --user-name copilot-readonly
  ```

  (Or leave the AWS fields blank to use your default `~/.aws` profile.)

## 3. Investigate

Send this in the chat bar:

> **ECS service api-prod in cluster api-prod-cluster returning 503s and high CPU for 20 minutes**

What you should see:

- **CloudWatch Logs** → finds the seeded 503/timeout/DB errors and summarizes the
  signature. This is the guaranteed signal that the live AWS read works.
- **Metrics** → CPU ~100% (critical), *if* the planner carries the cluster name
  into the metrics thread (see note). `AWS/ECS` CPU/Memory metrics require **both**
  the `ClusterName` and `ServiceName` dimensions, which is why the incident names
  the cluster explicitly. Give metrics a few minutes after deploy to populate.
- **Runbooks (RAG)** + **Code executor** run locally, then the **Synthesizer**
  emits the final `IncidentReport`.

> Note: the Metrics node only adds the `ClusterName` dimension when the planner
> puts the cluster in that thread's params. Naming the cluster in the incident
> makes that likely, but it's model-dependent — the Logs node is the
> deterministic part of this demo.

## 4. Tear down

```bash
bash demo/teardown.sh
```

Removes the ECS service, task, security group, IAM role, and the `/ecs/api-prod`
log group — nothing left running or billing.
