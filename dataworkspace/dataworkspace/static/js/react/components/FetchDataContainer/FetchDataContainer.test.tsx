import { render, waitFor } from '@testing-library/react';

import { fetchDataUsage } from '../../services';
import { DataDisplay, FetchDataContainer } from '../index';

describe('FetchDataContainer', () => {
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
      json: async () => ({
        page_views: 713
      })
    });
  };

  beforeEach(() => {
    mockFetch({});
  });

  afterAll(() => {
    global.fetch = globalFetch;
  });
  const setUp = () =>
    render(
      <FetchDataContainer
        fetchApi={() => fetchDataUsage('visualisation', '123')}
      >
        {(data) => <DataDisplay data={data} />}
      </FetchDataContainer>
    );

  it('should render a loading indicator', async () => {
    const { findByTitle } = setUp();
    expect(await findByTitle('Loading')).toBeInTheDocument();
  });

  it('should NOT render a loading indicator', async () => {
    const { queryByTitle } = setUp();
    waitFor(() => {
      expect(queryByTitle('Loading')).not.toBeInTheDocument();
    });
  });

  it('should render a component with data from an api', async () => {
    const { findByText } = setUp();
    expect(await findByText('Page views')).toBeInTheDocument();
  });

  it('should render an error message when the api fails', async () => {
    mockFetch({ status: 404, statusText: 'Not found', ok: false });
    const { findByText } = setUp();
    expect(await findByText('Error: 404 Not found')).toBeInTheDocument();
  });
});
