#!/usr/bin/env bash
# Deploy the copilot Fargate demo into your default VPC.
#   bash demo/deploy.sh            # uses ap-southeast-1
#   REGION=us-east-1 bash demo/deploy.sh
set -euo pipefail

REGION="${REGION:-ap-southeast-1}"
STACK="${STACK:-copilot-demo}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "Region: $REGION"

VPC=$(aws ec2 describe-vpcs --region "$REGION" \
  --filters Name=isDefault,Values=true \
  --query 'Vpcs[0].VpcId' --output text)

if [ -z "$VPC" ] || [ "$VPC" = "None" ]; then
  echo "No default VPC found in $REGION." >&2
  echo "Create one with:  aws ec2 create-default-vpc --region $REGION" >&2
  exit 1
fi

SUBNETS=$(aws ec2 describe-subnets --region "$REGION" \
  --filters Name=vpc-id,Values="$VPC" Name=default-for-az,Values=true \
  --query 'Subnets[].SubnetId' --output text | tr '\t' ',')

echo "VPC:     $VPC"
echo "Subnets: $SUBNETS"
echo

aws cloudformation deploy \
  --region "$REGION" \
  --stack-name "$STACK" \
  --template-file "$HERE/ecs-demo.yaml" \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides VpcId="$VPC" Subnets="$SUBNETS"

echo
echo "Stack outputs:"
aws cloudformation describe-stacks --region "$REGION" --stack-name "$STACK" \
  --query 'Stacks[0].Outputs' --output table

echo
echo "Give it ~3-5 min for the task to reach RUNNING and for AWS/ECS metrics to publish."
