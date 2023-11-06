import { fetchDataUsage, transformDataUsageResponse } from './services';

describe('transformDataUsageResponse', () => {
  const mockResponse = {
    page_views: 666,
    table_queries: 0.0,
    table_views: 0,
    collection_count: 1,
    bookmark_count: 0,
    dashboard_views: 0
  };
  it('should transform a data usage response', () => {
    const expected = [
      {
        label: 'Page views',
        value: 666
      },
      {
        label: 'Average daily users',
        value: 0
      },
      {
        label: 'Table views',
        value: 0
      },
      {
        label: 'Added to collections',
        value: 1
      },
      {
        label: 'Bookmarked by users',
        value: 0
      },
      {
        label: 'Dashboard views',
        value: 0
      }
    ];
    expect(transformDataUsageResponse(mockResponse)).toEqual(expected);
  });
});

describe('fetchDataUsage', () => {
  it('should return a response', async () => {
    const expected = [
      { label: 'Page views', value: 713 },
      { label: 'Average daily users', value: 0 },
      { label: 'Table views', value: 0 },
      { label: 'Added to collections', value: 1 },
      { label: 'Bookmarked by users', value: 0 }
    ];
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => ({
        page_views: 713,
        table_queries: 0.0,
        table_views: 0,
        collection_count: 1,
        bookmark_count: 0
      })
    });
    const response = await fetchDataUsage('datasets', '123');
    expect(response).toEqual(expected);
  });
  it('should throw a detailed error when the response returns an error', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'Not found',
      json: async () => {}
    });
    const response = await fetchDataUsage('datasets', '123');
    expect(response).toEqual(new Error('404 Not found'));
  });
  it('should throw a generic error when response fails', async () => {
    global.fetch = jest.fn().mockRejectedValue(() => Promise.reject());
    const response = await fetchDataUsage('datasets', '123');
    expect(response).toEqual(new Error('Oops! Something went wrong!'));
  });
});
