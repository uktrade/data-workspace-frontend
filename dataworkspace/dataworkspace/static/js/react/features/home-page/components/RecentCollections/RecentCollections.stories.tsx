import type { Meta, StoryObj } from '@storybook/react';

import type { Collection } from '.';
import RecentCollections from '.';

const collections: Collection[] = [
  {
    name: 'Interactions and service deliveries for companies between 2010 and 2023',
    url: '/some-collection-url'
  },
  {
    name: 'Data Workspace feedback banner results',
    url: '/some-collection-url'
  },
  {
    name: 'Jonathan’s personal collection',
    url: '/some-collection-url'
  }
];

const meta = {
  title: 'Recent Collections',
  component: RecentCollections
} satisfies Meta<typeof RecentCollections>;

type Story = StoryObj<typeof RecentCollections>;

export const withCollections: Story = {
  render: () => <RecentCollections collections={collections} />
};

export const noCollections: Story = {
  render: () => <RecentCollections collections={[]} />
};

export default meta;
