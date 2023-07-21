#
# Outputs a comma separated list of file extensions with the
# number of occurrences in an S3 bucket.
#
# To use set the BUCKET_NAME variable to the name of the bucket you're interested in
#
import csv
import os
import sys
from collections import defaultdict

import boto3

BUCKET_NAME = ""


def main():
    extensions = defaultdict(int)
    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET_NAME):
        for obj in page["Contents"]:
            extensions[os.path.splitext(obj["Key"])[-1]] += 1
    writer = csv.DictWriter(
        sys.stdout,
        fieldnames=[
            "extension",
            "num_files",
        ],
        quoting=csv.QUOTE_NONNUMERIC,
    )
    writer.writeheader()
    for ext, count in extensions.items():
        writer.writerow({"extension": ext, "num_files": count})


if __name__ == "__main__":
    main()
