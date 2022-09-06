import * as EventEmitter from "eventemitter3";
import { fileQueue } from "./utils";

export class Uploader extends EventEmitter {
  constructor(s3, options) {
    super(s3);

    this.s3 = s3;
    this.options = options;
    this.isAborted = false;
    this.remainingUploadCount = -1;

    this.uploads = [];
    console.log("options are", options);
  }

  cancel() {
    console.log("aborting ...");
    this.isAborted = true;
  }

  start(files, prefix) {
    const maxConnections = 4;
    const concurrentFiles = Math.min(maxConnections, files.length);
    const connectionsPerFile = Math.floor(maxConnections / concurrentFiles);
    this.queue = fileQueue(concurrentFiles);
    this.remainingUploadCount = files.length;

    // some v funky scope happening within the queue!
    // also this needs a rethink!
    const s3 = this.s3.s3;

    for (const file of files) {
      const params = {
        Bucket: this.options.bucketName,
        Key: prefix + file.relativePath,
        ContentType: file.type,
        Body: file,
      };

      const onProgress = (event) => {
        console.log("onProgress", file);
        const percent = event.total ? (event.loaded * 100.0) / event.total : 0;
        this.emit("upload:progress", file, percent);
      };

      this.queue(async () => {
        console.log("in task for", file.name);
        try {
          if (!this.isAborted) {
            this.emit("upload:start");
            let upload = s3.upload(params, {
              queueSize: connectionsPerFile,
            });
            console.log(upload);
            this.uploads.push(upload);
            console.log("about to await the upload");
            await upload.on("httpUploadProgress", onProgress).promise();
            this.emit("upload:complete", file);
          } else {
            this.emit("cancelled");
          }
        } catch (err) {
          console.error(err);
          if (this.isAborted) {
            this.emit("upload:failed", file);
          }
        } finally {
          this.remainingUploadCount--;
        }

        if (this.remainingUploadCount === 0) {
          this.emit("complete");
        }
      });
    }
  }
}
