#!/bin/bash
set -e

# Configuration
REGION="ap-northeast-1"
REPO_NAME="optinist-for-cloud-batch"
IMAGE_TAG="latest"
AWS_ACCOUNT_ID="637423646530"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${REGION}.amazonaws.com/${REPO_NAME}"

echo "Building and pushing batch image to ECR: $ECR_URI"

# Authenticate Docker to ECR
echo "Authenticating to ECR..."
aws ecr get-login-password --region $REGION | docker login --username AWS --password-stdin $ECR_URI

# Check if ECR repository exists, create if it doesn't
echo "Checking if ECR repository exists..."
if ! aws ecr describe-repositories --repository-names $REPO_NAME --region $REGION >/dev/null 2>&1; then
    echo "Repository $REPO_NAME does not exist. Creating..."
    aws ecr create-repository --repository-name $REPO_NAME --region $REGION
    echo "Repository $REPO_NAME created successfully."
else
    echo "Repository $REPO_NAME already exists."
fi

# Build the Docker image for batch workloads (no frontend build needed)
echo "Building batch Docker image..."
cd ../../../
docker build -f studio/config/docker/Dockerfile.batch -t $REPO_NAME:$IMAGE_TAG .

# Tag for ECR
docker tag $REPO_NAME:$IMAGE_TAG $ECR_URI:$IMAGE_TAG

# Push to ECR
echo "Pushing to ECR..."
docker push $ECR_URI:$IMAGE_TAG

echo "Successfully pushed $ECR_URI:$IMAGE_TAG"
