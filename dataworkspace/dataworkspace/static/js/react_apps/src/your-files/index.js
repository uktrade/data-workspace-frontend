import React from "react";
import ReactDOM from "react-dom";
import App from "./App";

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) {
  module.hot.accept();
}

const el = document.getElementById("your-files-app");

ReactDOM.render(
  <App
    config={YOURFILES_CONFIG}
  />,
  el
);
