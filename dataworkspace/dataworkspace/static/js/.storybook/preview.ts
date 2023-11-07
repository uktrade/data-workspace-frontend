import type { Preview } from '@storybook/react';

const CUSTOM_VIEWPORTS = {
  sml: {
    name: 'Small',
    styles: {
      width: '320px',
      height: '900px'
    }
  },
  md: {
    name: 'Medium',
    styles: {
      width: '641px',
      height: '900px'
    }
  },
  lg: {
    name: 'Large',
    styles: {
      width: '769px',
      height: '900px'
    }
  },
  xl: {
    name: 'XLarge',
    styles: {
      width: '1280px',
      height: '900px'
    }
  }
};

const preview: Preview = {
  parameters: {
    actions: { argTypesRegex: '^on[A-Z].*' },
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i
      }
    },
    viewport: {
      viewports: CUSTOM_VIEWPORTS,
      defaultViewport: 'xl'
    }
  }
};

export default preview;
