import AWS from "aws-sdk";

export class S3Proxy {
  constructor(config, s3) {
    this.config = config;
    this.s3 = s3;
  }
}

