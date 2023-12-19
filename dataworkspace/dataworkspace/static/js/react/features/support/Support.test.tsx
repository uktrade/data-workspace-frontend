import { render } from '@testing-library/react';

import Support from './Support';

describe('Support', () => {
  it('renders a H2 header', () => {
    const { getByRole } = render(<Support />);
    const header = getByRole('heading', {
      level: 2,
      name: 'How we can support you'
    });
    expect(header).toBeInTheDocument();
  });
  it('renders TilesContainer with GetHelp and OtherSupport components', () => {
    const { queryAllByRole } = render(<Support />);
    const headers = queryAllByRole('heading', { level: 3 });
    expect(headers.length).toBe(2);
  });
});
