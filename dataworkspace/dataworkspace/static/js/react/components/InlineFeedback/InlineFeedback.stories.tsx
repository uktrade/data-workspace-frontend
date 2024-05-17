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
    successMessage:
      'Thanks for letting us know, your response has been recorded',
    postFeedback: mockPostFeedback
  }
};

export const InlineFeedbackFormWithError: Story = {
  args: {
    title: 'Was this page helpful?',
    location: 'data-catalogue',
    successMessage:
      'Thanks for letting us know, your response has been recorded',
    postFeedback: mockRejectPostFeedback
  }
};

export const InlineFeedbackWithChildForm: Story = {
  render: (args) => {
    return (
      <InlineFeedback {...args}>
        {(location, wasItHelpful) => (
          <ChildForm location={location} wasItHelpful={wasItHelpful} />
        )}
      </InlineFeedback>
    );
  },
  args: {
    title: 'Was this page helpful?',
    location: 'data-catalogue',
    successMessage:
      'Thanks for letting us know, your response has been recorded',
    postFeedback: mockPostFeedback
  }
};
