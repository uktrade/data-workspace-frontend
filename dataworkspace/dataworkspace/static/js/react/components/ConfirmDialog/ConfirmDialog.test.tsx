import { fireEvent, render, screen } from '@testing-library/react';

import ConfirmDialog from './index';

describe('ConfirmDialog Modal Component', () => {
  const mockOnClose = jest.fn();
  const defaultProps = {
    actionUrl: '/submit-url',
    buttonText: 'Confirm',
    onClose: mockOnClose,
    open: false,
    title: 'Confirmation Dialog'
  };
  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders with correct title and button text', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    expect(screen.getByText('Confirmation Dialog')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeInTheDocument();
  });

  test('shows and hides the dialog based on the "open" prop', () => {
    const { rerender } = render(
      <ConfirmDialog {...defaultProps} open={false} />
    );
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();

    rerender(<ConfirmDialog {...defaultProps} open={true} />);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  test('submits form when the "Confirm" button is clicked', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    const form = screen.getByRole('form');
    form.onsubmit = jest.fn((e) => e.preventDefault());

    const confirmButton = screen.getByRole('button', { name: 'Confirm' });
    fireEvent.click(confirmButton);

    expect(form.onsubmit).toHaveBeenCalled();
    expect(confirmButton.onsubmit).toHaveBeenCalled();
  });

  test('calls onClose when the "Cancel" link is clicked', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    const cancelLink = screen.getByText('Cancel');
    fireEvent.click(cancelLink);

    expect(mockOnClose).toHaveBeenCalled();
  });

  test('form uses the correct action url parameter', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    const form = screen.getByRole('form');
    expect(form).toHaveAttribute('action', '/submit-url');
  });
});
