// @ts-ignore
import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { ConfirmDialog } from './index';

const meta = {
  title: 'ConfirmRemoveDialog',
  component: ConfirmDialog
} satisfies Meta<typeof ConfirmDialog>;

type Story = StoryObj<typeof ConfirmDialog>;

export const ConfirmRemoveUser: Story = {
  render: () => (
    <ConfirmDialog
      actionUrl="/submit"
      buttonText="Remove User?"
      onClose={() => {}}
      open={true}
      title="Are you sure you want to remove Jones?"
    />
  )
};

export default meta;
