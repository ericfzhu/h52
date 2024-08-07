#!/bin/bash

# Get the ECR repository URI
ECR_REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name H52-ecr \
  --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryUri'].OutputValue" \
  --output text)

# Deploy the main stack
sam deploy \
  --template-file template.yaml \
  --stack-name H52 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ECRRepositoryUri=$ECR_REPO_URI

echo "Hermes Inventory stack deployed"