import type { Meta, StoryObj } from '@storybook/react';

import type { RecentToolsProps } from '.';
import RecentTools from '.';

const meta = {
  title: 'Recent Tools',
  component: RecentTools
} satisfies Meta<typeof RecentTools>;

type Story = StoryObj<typeof RecentTools>;

const tools: RecentToolsProps[] = [
  {
    name: 'RStudio (R version 4)',
    url: '/url-1'
  },
  {
    name: 'JupyterLab Python',
    url: '/url-2'
  }
];

export const noTools: Story = {
  render: () => <RecentTools tools={[]} />
};

export const withTools: Story = {
  render: () => <RecentTools tools={tools} />
};

export default meta;
