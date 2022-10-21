import * as EventEmitter from "eventemitter3";
import { fileQueue } from "./utils";

const BULK_DELETE_MAX_FILES = 1000;

export class S3Deleter extends EventEmitter {
  constructor(s3, bucket) {
    super();

    this.s3 = s3;
    this.bucket = bucket;
  }


  start(folders, files) {
    const numObjects = folders.length + files.length;
    const maxConnections = 4;
    const queue = fileQueue(Math.min(maxConnections, numObjects));

    var isAborted = false;
    var remainingDeleteCount = numObjects;
    var keysToDelete = [];
    var filesToDelete = [];
    var foldersToDelete = [];

    const deleteKeys = async () => {
      let response;
      try {
        response = await this.s3
          .deleteObjects({
            Bucket: this.bucket,
            Delete: { Objects: keysToDelete.map((key) => ({ Key: key })) },
          })
          .promise();
      } catch (err) {
        console.error(err);
        throw err;
      } finally {
        keysToDelete = [];
      }
      return response;
    }

    const flushDelete = async () => {
      if (keysToDelete.length) return await deleteKeys();
    }

    const scheduleDelete = async (key) => {
      keysToDelete.push(key);
      if (keysToDelete.length > BULK_DELETE_MAX_FILES)
        return await deleteKeys();
    }

    for (const folder of folders) {
      queue(async () => {
        this.emit("delete:start", folder);
        let continuationToken = null;
        let isTruncated = true;
        while (isTruncated && !this.isAborted) {
          if (isAborted) {
            this.emit("delete:cancelled");
            return;
          }
          let response;
          try {
            response = await this.s3
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
            j < response.Contents.length && !isAborted;
            ++j
          ) {
            try {
              await scheduleDelete(response.Contents[j].Key);
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
      queue(async () => {
        this.emit("delete:start", file);
        try {
          await scheduleDelete(file.Key);
        } catch (err) {
          this.emit("delete:error", file);
        }
        this.emit("delete:finished", file);
      });
    }
    queue(async () => {
      await flushDelete();
      this.emit("delete:done");
    });

    return function() {
      isAborted = true;
    }
  }
}
