import { useEffect } from 'react';

import Button from '@govuk-react/button';
import Checkbox from '@govuk-react/checkbox';
import { H3 } from '@govuk-react/heading';

import type { FeedbackResponse } from '../../services/inline-feedback';

export const mockPostFeedback = (): Promise<FeedbackResponse> => {
  return new Promise((resolve) => {
    resolve({
      id: '123',
      location: 'some-location',
      was_this_page_helpful: true,
      inline_feedback_choices: '',
      more_detail: ''
    });
  });
};

export const mockRejectPostFeedback = (): Promise<FeedbackResponse> => {
  return new Promise((_resolve, reject) =>
    setTimeout(reject, 0, 'Oh no something went wrong!')
  );
};

export const ChildForm = ({
  wasItHelpful,
  resetForm
}: {
  wasItHelpful: boolean;
  resetForm: () => void;
}) => (
  <form data-testid="child-form">
    {wasItHelpful ? (
      <>
        <H3 size="SMALL">
          Thats great. Can you tell us more about this page? (optional)
        </H3>
        <Checkbox name="option">Yes option 1</Checkbox>
        <Checkbox name="option">Yes option 2</Checkbox>
      </>
    ) : (
      <>
        <H3 size="SMALL">
          Sorry to hear about that. How can we help make this page better?
          (optional)
        </H3>
        <Checkbox name="option">No option 1</Checkbox>
        <Checkbox name="option">No option 2</Checkbox>
      </>
    )}
    <br />
    <Button>Submit</Button>
    <Button
      onClick={(e) => {
        e.preventDefault();
        resetForm();
      }}
    >
      Reset
    </Button>
  </form>
);

export const EmptyChildForm = ({
  setSuccessMessage
}: {
  setSuccessMessage: (message: string) => void;
}) => {
  useEffect(() => {
    setSuccessMessage('Thanks for the additional feedback');
  }, []);
  return <form></form>;
};
