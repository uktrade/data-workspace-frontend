import { fireEvent, render, waitFor } from '@testing-library/react';

import type { InlineFeedbackProps } from '.';
import InlineFeedback from '.';
import {
  ChildForm,
  EmptyChildForm,
  mockPostFeedback,
  mockRejectPostFeedback
} from './mocks';

const props: InlineFeedbackProps = {
  csrf_token: '1234',
  title: 'Was this page helpful?',
  location: 'data-catalogue',
  postFeedback: mockPostFeedback
};

const setUpWithAdditonalForm = () =>
  render(
    <InlineFeedback {...props}>
      {(props) => <ChildForm {...props} />}
    </InlineFeedback>
  );

describe('InlineFeedback', () => {
  describe('without additional form', () => {
    it('should render a feedback question with two options', () => {
      const setUp = () => render(<InlineFeedback {...props} />);
      const { getByRole } = setUp();
      expect(
        getByRole('heading', {
          name: 'Was this page helpful?',
          level: 2
        })
      ).toBeInTheDocument();
      expect(getByRole('button', { name: 'Yes' })).toBeInTheDocument();
      expect(getByRole('button', { name: 'No' })).toBeInTheDocument();
    });
    it('should render a success message when an option is submitted', async () => {
      const setUp = () => render(<InlineFeedback {...props} />);
      const { getByRole } = setUp();
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Thanks for letting us know, your response has been recorded.',
            level: 2
          })
        ).toBeInTheDocument();
      });
    });
    it('should render a custom success message when an option is submitted', async () => {
      const setUp = () =>
        render(
          <InlineFeedback
            {...props}
            customSuccessMessage="Great thanks for that."
          />
        );
      const { getByRole } = setUp();
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Great thanks for that.',
            level: 2
          })
        ).toBeInTheDocument();
      });
    });
  });
  describe('with additional form', () => {
    it('should render a second form after the "yes" button has been submitted', async () => {
      const { getByRole } = setUpWithAdditonalForm();
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Thanks for letting us know, your response has been recorded.',
            level: 2
          })
        ).toBeInTheDocument();
        expect(
          getByRole('heading', {
            name: 'Thats great. Can you tell us more about this page? (optional)',
            level: 3
          })
        ).toBeInTheDocument();
        expect(
          getByRole('checkbox', {
            name: 'Yes option 1'
          })
        ).toBeInTheDocument();
        expect(
          getByRole('checkbox', {
            name: 'Yes option 2'
          })
        ).toBeInTheDocument();
      });
    });
    it('should render a second form after the "no" button has been submitted', async () => {
      const { getByRole } = setUpWithAdditonalForm();
      fireEvent.click(getByRole('button', { name: 'No' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Thanks for letting us know, your response has been recorded.',
            level: 2
          })
        ).toBeInTheDocument();
        expect(
          getByRole('heading', {
            name: 'Sorry to hear about that. How can we help make this page better? (optional)',
            level: 3
          })
        ).toBeInTheDocument();
        expect(
          getByRole('checkbox', {
            name: 'No option 1'
          })
        ).toBeInTheDocument();
        expect(
          getByRole('checkbox', {
            name: 'No option 2'
          })
        ).toBeInTheDocument();
      });
    });
    it('should alter the success message when the child form updates it', async () => {
      const { getByRole, queryByRole } = render(
        <InlineFeedback {...props}>
          {(props) => <EmptyChildForm {...props} />}
        </InlineFeedback>
      );
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Thanks for the additional feedback',
            level: 2
          })
        ).toBeInTheDocument();
        expect(
          queryByRole('heading', {
            name: 'Thanks for letting us know, your response has been recorded.',
            level: 2
          })
        ).not.toBeInTheDocument();
      });
    });
    it('should reset the form if the reset button is clicked', async () => {
      const { queryByTestId, getByRole } = setUpWithAdditonalForm();
      expect(queryByTestId('child-form')).not.toBeInTheDocument();
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(queryByTestId('child-form')).toBeInTheDocument();
      });
      fireEvent.click(getByRole('button', { name: 'Reset' }));
      expect(queryByTestId('child-form')).not.toBeInTheDocument();
    });
  });
  describe('with error', () => {
    it('should render an error message if the submission was to fail', async () => {
      const setUp = () =>
        render(
          <InlineFeedback
            {...props}
            postFeedback={mockRejectPostFeedback}
            csrf_token="1234"
          />
        );
      const { getByRole, getByText } = setUp();
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(
          getByText('Error: Oh no something went wrong!')
        ).toBeInTheDocument();
      });
    });
  });
});
