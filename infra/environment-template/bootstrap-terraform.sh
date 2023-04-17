#!/bin/bash
################################################################################
# Functions                                                                    #
################################################################################
show_help()
{
   # Display help
   printf "
Configures an AWS S3 bucket for deploying Data Workspace using Terraform.

bootstrap-terraform --profile <value> --bucket <value> --region <value>

profile    Select the AWS profile name to use
bucket     Set the name of the S3 bucket and dynamodb table
region     Set the region of the S3 bucket and dynamodb table
help       Print this help

"
}
die() {
    printf '%s\n' "$1" >&2
    exit 1
}

################################################################################
# Process arguments                                                            #
################################################################################
# http://mywiki.wooledge.org/BashFAQ/035
while :; do
    case $1 in
        -h|-\?|--help)
            show_help
            exit
            ;;
        -b|--bucket)
            if [ "$2" ]; then
                bucket=$2
                shift
            else
                die 'ERROR: "--bucket" requires a non-empty option argument.'
            fi
            ;;
        -p|--profile)
            if [ "$2" ]; then
                profile=$2
                shift
            else
                die 'ERROR: "--profile" requires a non-empty option argument.'
            fi
            ;;
        -r|--region)
            if [ "$2" ]; then
                region=$2
                shift
            else
                die 'ERROR: "--region" requires a non-empty option argument.'
            fi
            ;;
        --)
            shift
            break
            ;;
        -?*)
            printf 'WARN: Unknown option (ignored): %s\n' "$1" >&2
            ;;
        *)
            break
    esac

    shift
done

################################################################################
# Core script                                                                  #
################################################################################
aws s3api create-bucket \
    --bucket $bucket \
    --region $region \
    --create-bucket-configuration LocationConstraint=$region \
    --profile $profile
aws dynamodb create-table \
    --attribute-definitions \
        AttributeName=LockID,AttributeType=S \
    --table-name $bucket-lock \
    --key-schema \
        AttributeName=LockID,KeyType=HASH \
    --region $region \
    --provisioned-throughput \
        ReadCapacityUnits=20,WriteCapacityUnits=20 \
    --profile $profile

printf "terraform {
  backend "s3" {
    region         = $region
    encrypt        = true
    bucket         = $bucket
    key            = ${PWD##*/}/terraform.tfstate
    dynamodb_table = $bucket-lock
  }
}"
