import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import YourFiles from './YourFiles';

if (module.hot) {
  module.hot.accept();
}

const rootElement = document.getElementById('your-files-app');
const root = createRoot(rootElement);

root.render(
  <StrictMode>
    {/* eslint-disable-next-line no-undef */}
    <YourFiles config={YOURFILES_CONFIG} />
  </StrictMode>
);
