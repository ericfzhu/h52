#!/bin/bash

# Get the ECR repository URI
ECR_REPO_URI=$(aws cloudformation describe-stacks \
  --stack-name H52-ecr \
  --query "Stacks[0].Outputs[?OutputKey=='ECRRepositoryUri'].OutputValue" \
  --output text)

# Authenticate Docker to ECR
aws ecr get-login-password --region $(aws configure get region) | docker login --username AWS --password-stdin $ECR_REPO_URI

# Build Docker image
docker build -t hermes-inventory .

# Tag image for ECR
docker tag hermes-inventory:latest $ECR_REPO_URI:latest

# Push image to ECR
docker push $ECR_REPO_URI:latest

echo "Image pushed to $ECR_REPO_URI:latest"