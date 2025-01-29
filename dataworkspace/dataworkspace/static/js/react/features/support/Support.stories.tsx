// @ts-ignore
import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import SupportYou from './Support';

const meta = {
  title: 'Support Your feature',
  component: SupportYou
} satisfies Meta<typeof SupportYou>;

type Story = StoryObj<typeof SupportYou>;

export const WithTiles: Story = {
  render: () => <SupportYou />
};

export default meta;
