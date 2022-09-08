import * as EventEmitter from "eventemitter3";
import { fileQueue } from "./utils";

const BULK_DELETE_MAX_FILES = 1000;

export class S3Deleter extends EventEmitter {
  constructor(s3, bucket) {
    super();

    this.s3 = s3;
    this.bucket = bucket;
    this.isAborted = false;
    this.remainingDeleteCount = -1;
    this.keysToDelete = [];
    this.filesToDelete = [];
    this.foldersToDelete = [];
  }

  cancel() {
    this.isAborted = true;
  }

  async deleteKeys() {
    let response;
    try {
      response = await this.s3.deleteObjects(this.bucket, this.keysToDelete);
    } catch (err) {
      console.error(err);
      throw err;
    } finally {
      this.keysToDelete = [];
    }
    return response;
  }

  async scheduleDelete(key) {
    this.keysToDelete.push(key);
    if (this.keysToDelete.length > BULK_DELETE_MAX_FILES)
      return await this.deleteKeys();
  }

  async flushDelete() {
    if (this.keysToDelete.length) return await this.deleteKeys();
  }

  start(folders, files) {
    const numObjects = folders.length + files.length;
    const maxConnections = 4;
    this.queue = fileQueue(Math.min(maxConnections, numObjects));
    this.remainingDeleteCount = numObjects;
    const s3 = this.s3.s3;
    for (const folder of folders) {
      this.queue(async () => {
        this.emit("delete:start", folder);
        let continuationToken = null;
        let isTruncated = true;
        while (isTruncated && !this.isAborted) {
          if (this.isAborted) {
            this.emit("delete:cancelled");
            return;
          }
          let response;
          try {
            response = await s3
              .listObjects({
                Bucket: this.bucket,
                Prefix: folder.Prefix,
                ContinuationToken: continuationToken,
              })
              .promise();
            continuationToken = response.NextContinuationToken;
            isTruncated = response.IsTruncated;
          } catch (err) {
            console.error(err);
            this.emit("delete:error", folder, err.code || err.message || err);
            return;
          }
          // Loop through the objects within the prefix and bulk delete them
          for (
            let j = 0;
            j < response.Contents.length && !this.isAborted;
            ++j
          ) {
            try {
              await this.scheduleDelete(response.Contents[j].Key);
            } catch (err) {
              this.emit("delete:error", folder);
              break;
            }
          }
          this.emit("delete:finished", folder);
        }
      });
    }
    for (const file of files) {
      this.queue(async () => {
        this.emit("delete:start", file);
        try {
          await this.scheduleDelete(file.Key);
        } catch (err) {
          this.emit("delete:error", file);
        }
        this.emit("delete:finished", file);
      });
    }
    this.queue(async () => {
      await this.flushDelete();
      this.emit("delete:done");
    });
  }
}
