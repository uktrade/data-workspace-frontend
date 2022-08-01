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
    console.log("refresh");
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

    const now = new Date();
    this.expiration = new Date(
      now.getFullYear() - 1,
      now.getMonth(),
      now.getDay()
    );
    callback();
  }

  needsRefresh() {
    return this.expiration - 60 < Date.now();
  }
}

export class S3Proxy {
  constructor(config) {
    console.log(config);

    AWS.config.update({
      credentials: new Credentials(config),
      region: config.region,
    });

    // const ep = new AWS.Endpoint("http://localhost:9000");
    if (config.endpointUrl) {
      console.log(`using ${config.endpointUrl} for endpoint`);
      AWS.config.update({
        endpoint: config.endpointUrl,
      });
    }

    this.s3 = new AWS.S3({ s3ForcePathStyle: true });
  }

  enrichObjectContents(data) {
    data.Contents.forEach((d) => {
      d.isCsv = d.Key.substr(d.Key.length - 3, d.Key.length) === "csv";
      d.formattedDate = new Date(d.LastModified);
    });
    return data;
  }

  async listObjects(params) {
    try {
      const response = await this.s3.listObjectsV2(params).promise();
      const data = this.enrichObjectContents(response);
      return data;
    } catch (err) {
      console.error(err);
      throw err;
    }
  }
}
