#!/usr/bin/env bash
# Tear down the copilot Fargate demo (stops the task, removes everything).
#   bash demo/teardown.sh
set -euo pipefail

REGION="${REGION:-ap-southeast-1}"
STACK="${STACK:-copilot-demo}"

echo "Deleting stack '$STACK' in $REGION (removes the ECS service, task, and /ecs/api-prod log group)…"
aws cloudformation delete-stack --region "$REGION" --stack-name "$STACK"
aws cloudformation wait stack-delete-complete --region "$REGION" --stack-name "$STACK"
echo "Done. Nothing left running."
