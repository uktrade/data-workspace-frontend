/* eslint-disable no-undef */
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import YourFiles from './YourFiles';

const rootElement = document.getElementById('your-files-app-v2')!;
const root = createRoot(rootElement);

root.render(
  <StrictMode>
    {/* @ts-ignore */}
    <YourFiles config={YOURFILES_CONFIG} />
  </StrictMode>
);
