import { fireEvent, render, screen } from '@testing-library/react';

import ConfirmDialog from './index';

describe('ConfirmDialog Modal Component', () => {
  const mockOnClose = jest.fn();
  const defaultProps = {
    actionUrl: '/submit-url',
    bodyText: '""',
    buttonTextAccept: 'Confirm',
    buttonTextCancel: 'Cancel',
    buttonValueAccept: '',
    csrf_token: '123',
    onClose: mockOnClose,
    open: false,
    title: 'Confirmation Dialog',
    warning: false
  };
  afterEach(() => {
    jest.clearAllMocks();
  });
  beforeAll(() => {
    HTMLDialogElement.prototype.show = jest.fn(function mock(
      this: HTMLDialogElement
    ) {
      this.open = true;
    });

    HTMLDialogElement.prototype.showModal = jest.fn(function mock(
      this: HTMLDialogElement
    ) {
      this.open = true;
    });

    HTMLDialogElement.prototype.close = jest.fn(function mock(
      this: HTMLDialogElement
    ) {
      this.open = false;
    });
  });

  it('renders with correct title and button text', () => {
    const { getByRole } = render(
      <ConfirmDialog {...defaultProps} open={true} />
    );
    expect(getByRole('heading'));
    expect(getByRole('button'));
  });

  test('shows and hides the dialog based on the "open" prop', () => {
    const { rerender } = render(
      <ConfirmDialog {...defaultProps} open={false} />
    );
    expect(screen.queryByRole('dialog', { hidden: true })).not.toBeVisible();

    rerender(<ConfirmDialog {...defaultProps} open={true} />);
    expect(screen.getByRole('dialog', { hidden: true })).toBeInTheDocument();
  });

  test('submits form when the "Confirm" button is clicked', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    const form = screen.getByRole('form');
    form.onsubmit = jest.fn((e) => e.preventDefault());

    const confirmButton = screen.getByRole('button');
    fireEvent.click(confirmButton);

    expect(form.onsubmit).toHaveBeenCalled();
  });

  test('calls onClose when the "Cancel" link is clicked', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    const cancelLink = screen.getByRole('link');
    fireEvent.click(cancelLink);

    expect(mockOnClose).toHaveBeenCalled();
  });

  test('form uses the correct action url parameter', () => {
    render(<ConfirmDialog {...defaultProps} open={true} />);

    const form = screen.getByRole('form');
    expect(form).toHaveAttribute('action', '/submit-url');
  });

  it('renders with correct width based on "warning" prop', () => {
    const { rerender } = render(
      <ConfirmDialog {...defaultProps} open={true} warning={false} />
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveStyle('width: 600px');

    rerender(<ConfirmDialog {...defaultProps} open={true} warning={true} />);
    expect(dialog).toHaveStyle('width: 659px'); // width when warning is true
  });
});
