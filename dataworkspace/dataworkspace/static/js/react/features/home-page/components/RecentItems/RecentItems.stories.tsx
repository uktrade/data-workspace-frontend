// @ts-ignore
import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import type { RecentItemProps } from '.';
import RecentItems from '.';

const meta = {
  title: 'Recent Items',
  component: RecentItems
} satisfies Meta<typeof RecentItems>;

type Story = StoryObj<typeof RecentItems>;

const items: RecentItemProps[] = [
  {
    url: '/some-url',
    name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
  },
  {
    url: '/some-url',
    name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
  },
  {
    url: '/some-url',
    name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
  },
  {
    url: '/some-url',
    name: 'Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua'
  }
];

export const withItems: Story = {
  render: () => <RecentItems items={items} />
};

export const noItems: Story = {
  render: () => <RecentItems items={[]} />
};

export default meta;
