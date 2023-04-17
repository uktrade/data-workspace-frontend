#!/bin/bash
printf "Enter yout AWS CLI SSO profile name: "
read aws_profile
printf "Name your S3 bucket: "
read s3_bucket

aws_region=$(aws configure get region --profile $aws_profile)

aws s3api create-bucket \
    --bucket $s3_bucket \
    --region $aws_region \
    --create-bucket-configuration LocationConstraint=$aws_region \
    --profile $aws_profile
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=LockID,AttributeType=S \
    --table-name $s3_bucket-lock \
    --key-schema \
        AttributeName=LockID,KeyType=HASH \
    --region $aws_region \
    --provisioned-throughput \
        ReadCapacityUnits=20,WriteCapacityUnits=20 \
    --profile $aws_profile

printf "terraform {
  backend "s3" {
    region         = $aws_region
    encrypt        = true
    bucket         = $s3_bucket
    key            = ${PWD##*/}/terraform.tfstate
    dynamodb_table = $s3_bucket-lock
  }
}"
