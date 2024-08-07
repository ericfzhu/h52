#!/bin/bash

# Deploy ECR repository
aws cloudformation deploy \
  --template-file ecr-template.yaml \
  --stack-name H52-ecr \
  --capabilities CAPABILITY_IAM

# Get the ECR repository URI
ECR_REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name H52-ecr \
  --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryUri'].OutputValue" \
  --output text)

echo "ECR Repository URI: $ECR_REPO_URI"