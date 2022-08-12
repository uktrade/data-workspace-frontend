import * as EventEmitter from "eventemitter3";

export class Uploader extends EventEmitter {
  constructor(s3, options) {
    super(s3);
    this.s3 = s3;
    this.options = options;
  }

  start(files) {
    console.log("start");
    for (const file of files) {
      const params = {
        Bucket: model.bucket,
        Key: model.currentPrefix + file.relativePath,
        ContentType: file.type,
        Body: file,
      };
      this.emit("upload:start", file);
    }
  }
}
