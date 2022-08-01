import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) {
  module.hot.accept();
}

const el = document.getElementById("your-files-app");
const root = createRoot(el);

root.render(<App />);
