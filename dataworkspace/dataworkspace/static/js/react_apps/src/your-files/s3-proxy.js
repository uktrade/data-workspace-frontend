import AWS from "aws-sdk";

export class S3Proxy {
  constructor(config, s3) {
    this.config = config;
    this.s3 = s3;
  }

  async deleteObjects(bucket, keys) {
    return this.s3
      .deleteObjects({
        Bucket: bucket,
        Delete: { Objects: keys.map((key) => ({ Key: key })) },
      })
      .promise();
  }
}
