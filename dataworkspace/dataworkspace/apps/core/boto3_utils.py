import boto3

def boto3_client_s3():
    return boto3.client("s3")

def boto3_client_iam():
    return boto3.client("iam")