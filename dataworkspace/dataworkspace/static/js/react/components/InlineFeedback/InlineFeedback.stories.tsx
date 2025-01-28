// @ts-ignore
import React from 'react';

import type { Meta, StoryObj } from '@storybook/react';

import { InlineFeedback } from '../index';
import { ChildForm, mockPostFeedback, mockRejectPostFeedback } from './mocks';

const meta = {
  title: 'Forms',
  component: InlineFeedback
} satisfies Meta<typeof InlineFeedback>;
export default meta;

type Story = StoryObj<typeof InlineFeedback>;

export const InlineFeedbackForm: Story = {
  args: {
    title: 'Was this page helpful?',
    location: 'data-catalogue',
    postFeedback: mockPostFeedback,
    csrf_token: '1234'
  }
};

export const InlineFeedbackFormWithError: Story = {
  args: {
    title: 'Was this page helpful?',
    location: 'data-catalogue',
    postFeedback: mockRejectPostFeedback,
    csrf_token: '1234'
  }
};

export const InlineFeedbackWithChildForm: Story = {
  render: (args) => {
    return (
      <InlineFeedback {...args}>
        {(props) => <ChildForm {...props} />}
      </InlineFeedback>
    );
  },
  args: {
    title: 'Was this page helpful?',
    location: 'data-catalogue',
    postFeedback: mockPostFeedback
  }
};
