import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import YourFiles from './YourFiles';

// Workaround for hot reload "ignored-module" issue when developing locally.
if (module.hot) {
  module.hot.accept();
}

const rootElement = document.getElementById('your-files-app');
const root = createRoot(rootElement);

root.render(
  <StrictMode>
    <YourFiles config={YOURFILES_CONFIG} />
  </StrictMode>
);
