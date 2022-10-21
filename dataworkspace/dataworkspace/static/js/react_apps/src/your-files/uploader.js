import * as EventEmitter from "eventemitter3";
import { fileQueue } from "./utils";

export class Uploader extends EventEmitter {
  constructor(s3, options) {
    super(s3);

    this.s3 = s3;
    this.options = options;

    console.log("options are", options);
  }

  start(files, prefix) {
    var isAborted = false;
    var remainingUploadCount = files.length;
    var uploads = [];

    const maxConnections = 4;
    const concurrentFiles = Math.min(maxConnections, files.length);
    const connectionsPerFile = Math.floor(maxConnections / concurrentFiles);
    const queue = fileQueue(concurrentFiles);

    // some v funky scope happening within the queue!
    // also this needs a rethink!
    const s3 = this.s3;

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

      queue(async () => {
        console.log("in task for", file.name);
        try {
          if (!isAborted) {
            this.emit("upload:start");
            let upload = s3.upload(params, {
              queueSize: connectionsPerFile,
            });
            console.log(upload);
            uploads.push(upload);
            console.log("about to await the upload");
            await upload.on("httpUploadProgress", onProgress).promise();
            this.emit("upload:complete", file);
          } else {
            this.emit("cancelled");
          }
        } catch (err) {
          console.error(err);
          if (isAborted) {
            this.emit("upload:failed", file);
          }
        } finally {
          remainingUploadCount--;
        }

        if (remainingUploadCount === 0) {
          this.emit("complete");
        }
      });
    }

    return function() {
      console.log("aborting ...");
      isAborted = true;
      uploads.forEach((upload) => {
        upload.abort();
      });
    }
  }
}
