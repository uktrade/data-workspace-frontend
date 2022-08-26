const BULK_DELETE_MAX_FILES = 1000;

export class S3Deleter {
  constructor(s3, bucket) {
    this.s3 = s3;
    this.bucket = bucket;
    this.keys = [];
  }

  deleteKeys = async () => {
    let response;
    try {
      response = await this.s3
        .deleteObjects({ Bucket: this.bucket, Delete: { Objects: this.keys } })
        .promise();
    } catch (err) {
      console.error(err);
      throw err;
    } finally {
      this.keys = [];
    }
    return response;
  };

  scheduleDelete = async (key) => {
    this.keys.push({ Key: key });
    if (this.keys.length >= BULK_DELETE_MAX_FILES)
      return await this.deleteKeys();
  };

  flushDelete = async () => {
    if (this.keys.length) return await this.deleteKeys();
  };
}
