import type { Meta, StoryObj } from '@storybook/react';

import GetInTouch from '.';

const meta = {
  title: 'Get in touch tile'
} satisfies Meta<typeof GetInTouch>;

type Story = StoryObj<typeof GetInTouch>;

export const WithContent: Story = {
  render: () => <GetInTouch />
};

export default meta;
