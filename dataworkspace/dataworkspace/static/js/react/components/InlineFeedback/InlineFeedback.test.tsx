import { fireEvent, render, waitFor } from '@testing-library/react';

import InlineFeedback from '.';
import { ChildForm, mockPostFeedback, mockRejectPostFeedback } from './mocks';

const props = {
  title: 'Was this page helpful?',
  location: 'data-catalogue',
  successMessage: 'Thanks for letting us know, your response has been recorded',
  postFeedback: mockPostFeedback
};

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
            name: 'Thanks for letting us know, your response has been recorded',
            level: 2
          })
        ).toBeInTheDocument();
      });
    });
  });
  describe('with additional form', () => {
    it('should render a second form after the "yes" button has been submitted', async () => {
      const setUp = () =>
        render(
          <InlineFeedback {...props}>
            {(location, wasItHelpful) => (
              <ChildForm location={location} wasItHelpful={wasItHelpful} />
            )}
          </InlineFeedback>
        );
      const { getByRole } = setUp();
      fireEvent.click(getByRole('button', { name: 'Yes' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Thanks for letting us know, your response has been recorded',
            level: 2
          })
        ).toBeInTheDocument();
        expect(
          getByRole('heading', {
            name: 'Thats great. Can you tell us more about the data-catalogue page? (optional)',
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
      const setUp = () =>
        render(
          <InlineFeedback {...props}>
            {(location, wasItHelpful) => (
              <ChildForm location={location} wasItHelpful={wasItHelpful} />
            )}
          </InlineFeedback>
        );
      const { getByRole } = setUp();
      fireEvent.click(getByRole('button', { name: 'No' }));
      await waitFor(() => {
        expect(
          getByRole('heading', {
            name: 'Thanks for letting us know, your response has been recorded',
            level: 2
          })
        ).toBeInTheDocument();
        expect(
          getByRole('heading', {
            name: 'Sorry to hear about that. How can we help make the data-catalogue page better? (optional)',
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
  });
  describe('with error', () => {
    it('should render an error message if the submission was to fail', async () => {
      const setUp = () =>
        render(
          <InlineFeedback {...props} postFeedback={mockRejectPostFeedback} />
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
