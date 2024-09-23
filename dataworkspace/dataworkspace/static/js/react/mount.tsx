// @ts-nocheck
import React, { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

const mount = (Component: React.ElementType, id: string) => {
  const rootElement = document.getElementById(id)!;
  const dataProps = rootElement.getAttribute('data-props');
  const props = dataProps ? JSON.parse(dataProps) : {};
  const root = createRoot(rootElement);

  root.render(<Component {...props} />);
};

export default mount;
