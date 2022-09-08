import AWS from "aws-sdk";

function fetchJSON(url) {
  return new Promise((resolve, reject) => {
    function resolveJSON() {
      resolve(JSON.parse(oReq.responseText));
    }

    var oReq = new XMLHttpRequest();
    oReq.addEventListener("load", resolveJSON);
    oReq.addEventListener("error", reject);
    oReq.open("GET", url);
    oReq.send();
  });
}

class Credentials extends AWS.Credentials {
  constructor(config) {
    super();
    this.expiration = 0;
    this.config = config;
  }

  async refresh(callback) {
    try {
      const response = await fetchJSON(this.config.credentialsUrl);
      this.accessKeyId = response.AccessKeyId;
      this.secretAccessKey = response.SecretAccessKey;
      this.sessionToken = response.SessionToken;
      this.expiration = Date.parse(response.Expiration);
    } catch (err) {
      callback(err);
      return;
    }

    callback();
  }

  needsRefresh() {
    return this.expiration - 60 < Date.now();
  }
}

export class S3Proxy {
  constructor(config) {
    this.config = config;
    console.log(this.config);
    AWS.config.update({
      credentials: new Credentials(config),
      region: config.region,
    });

    if (config.endpointUrl) {
      console.log(`using ${config.endpointUrl} for endpoint`);
      AWS.config.update({
        endpoint: config.endpointUrl,
      });
    }

    this.s3 = new AWS.S3({ s3ForcePathStyle: true });
  }

  async listObjects(params) {
    const response = await this.s3.listObjectsV2(params).promise();
    const files = response.Contents.filter((file) => {
      return file.Key !== params.Prefix;
    }).map((file) => {
      file.isCsv =
        file.Key.substr(file.Key.length - 3, file.Key.length) === "csv";
      file.formattedDate = new Date(file.LastModified);
      return file;
    });

    const folders = [];
    if (params.Prefix === this.config.initialPrefix) {
      folders.push({
        Prefix: this.config.initialPrefix + this.config.bigdataPrefix,
        isBigData: true,
      });
    }

    const commonFolders = response.CommonPrefixes.filter((folder) => {
      return (
        folder.Prefix !==
        `${this.config.initialPrefix}${this.config.bigdataPrefix}`
      );
    }).map((folder) => {
      folder.isBigData = false;
      return folder;
    });

    folders.push(...commonFolders);

    return {
      files,
      folders,
    };
  }

  getSignedUrl(params) {
    return this.s3.getSignedUrlPromise("getObject", params);
  }

  removeSlashes(text) {
    return text.replace(/^\/+/g, "").replace(/\/+$/g, "");
  }

  async createFolder(prefix, folderName) {
    console.log("createFolder", prefix, folderName);
    const folder = prefix + this.removeSlashes(folderName) + "/";
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
