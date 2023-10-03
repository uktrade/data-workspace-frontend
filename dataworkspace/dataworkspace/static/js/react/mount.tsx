import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

const mount = (Component: React.ElementType, id: string) => {
  const rootElement = document.getElementById(id)!;
  const root = createRoot(rootElement);

  root.render(
    <StrictMode>
      <Component />
    </StrictMode>
  );
};

export default mount;
