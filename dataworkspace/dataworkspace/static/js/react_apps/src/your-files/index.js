import React from "react";
import ReactDOM from "react-dom";
import App from "./App";
import { Uploader } from "./uploader";
import { S3Proxy } from "./s3-proxy";
import { S3Deleter } from "./s3-deleter";

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) {
  module.hot.accept();
}

const el = document.getElementById("your-files-app");

const proxy = new S3Proxy(YOURFILES_CONFIG);

const uploader = new Uploader(proxy, {
  bucketName: YOURFILES_CONFIG.bucketName,
});

const deleter = new S3Deleter(proxy, YOURFILES_CONFIG.bucketName);

ReactDOM.render(
  <App
    proxy={proxy}
    config={YOURFILES_CONFIG}
    uploader={uploader}
    deleter={deleter}
  />,
  el
);
