import { render, waitFor } from '@testing-library/react';

import HomePage from './HomePage';

describe('HomePage', () => {
  const globalFetch = global.fetch;

  type MockFetchProps = {
    ok?: boolean;
    status?: number;
    statusText?: string;
  };

  const mockFetch = ({
    ok = true,
    status = 200,
    statusText = 'status text message'
  }: MockFetchProps): void => {
    global.fetch = jest.fn().mockResolvedValue({
      ok,
      status,
      statusText,
      json: async () => {
        return { results: [] };
      }
    });
  };

  beforeEach(() => {
    mockFetch({});
  });

  afterAll(() => {
    global.fetch = globalFetch;
  });

  it('should render a main container', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(getByRole('main')).toBeInTheDocument();
    });
  });
  it('should render 6 articles', async () => {
    const { getAllByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(getAllByRole('article')).toHaveLength(7);
    });
  });
  it('should render managed data', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('link', { name: 'View and manage your data' })
      ).toBeInTheDocument();
    });
  });
  it('should render your recent items', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('heading', { name: 'Your recent items', level: 2 })
      ).toBeInTheDocument();
    });
  });
  it('should render your recent collections', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('heading', { name: 'Your recent collections', level: 2 })
      ).toBeInTheDocument();
    });
  });
  it('should render your recent tools', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('heading', { name: 'Your recent tools', level: 2 })
      ).toBeInTheDocument();
    });
  });
  it('should render your recent bookmarks', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('heading', { name: 'Your bookmarks', level: 2 })
      ).toBeInTheDocument();
    });
  });
  it('should render get help', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('heading', { name: 'Get help', level: 3 })
      ).toBeInTheDocument();
    });
  });
  it('should render get in touch', async () => {
    const { getByRole } = render(<HomePage />);
    await waitFor(() => {
      expect(
        getByRole('heading', { name: 'Get in touch', level: 3 })
      ).toBeInTheDocument();
    });
  });
});
