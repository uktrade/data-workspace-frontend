import AWS from "aws-sdk";

export class S3Proxy {
  constructor(config, s3) {
    this.config = config;
    this.s3 = s3;
  }

  getSignedUrl(params) {
    return this.s3.getSignedUrlPromise("getObject", params);
  }

  async createFolder(prefix, folderName) {
    const removeSlashes = (text) => {
      return text.replace(/^\/+/g, "").replace(/\/+$/g, "");
    }

    console.log("createFolder", prefix, folderName);
    const folder = prefix + removeSlashes(folderName) + "/";
    console.log(folder);
    const params = { Bucket: this.config.bucketName, Key: folder };
    let canCreate = false;

    // Slightly awkward since a 404 is converted to an exception
    try {
      await this.s3.headObject(params).promise();
    } catch (err) {
      canCreate = err.code === "NotFound";
      if (!canCreate) {
        throw err;
      }
    }
    if (!canCreate) {
      alert("Error: folder or object already exists at " + params.Key);
      return;
    }

    await this.s3.putObject(params).promise();
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
