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
    console.log("refreshing AWS credentials");
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
    console.log(params);
    try {
      const response = await this.s3.listObjectsV2(params).promise();
      const files = response.Contents.filter((file) => {
        return file.Key !== params.Prefix;
      }).map((file) => {
        file.isCsv =
          file.Key.substr(file.Key.length - 3, file.Key.length) === "csv";
        file.formattedDate = new Date(file.LastModified);
        return file;
      });

      const folders = response.CommonPrefixes.filter((prefix) => {
        return prefix.Prefix != this.config.Prefix + this.config.bigdataPrefix;
      });

      return {
        files,
        folders,
      };
    } catch (err) {
      console.error(err);
      throw err;
    }
  }

  getSignedUrl(params) {
    return this.s3.getSignedUrlPromise("getObject", params);
  }
}
