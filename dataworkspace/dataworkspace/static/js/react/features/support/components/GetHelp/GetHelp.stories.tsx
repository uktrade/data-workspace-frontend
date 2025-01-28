// @ts-ignore
import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import GetHelp from '.';

const meta = {
  title: 'Get Help tile',
  component: GetHelp
} satisfies Meta<typeof GetHelp>;

type Story = StoryObj<typeof GetHelp>;

export const WithContent: Story = {
  render: () => <GetHelp />
};

export default meta;
