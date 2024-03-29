import {
  ApiError,
  fetchDataUsage,
  fetchRecentCollections,
  fetchRecentItems,
  fetchYourBookmarks,
  fetchYourRecentTools
} from './';
import {
  dataUsage,
  recentCollections,
  recentItems,
  yourBookmarks,
  yourRecentTools
} from './mocks';

describe('fetchDataUsage', () => {
  it('should return a transformed response', async () => {
    const expected = [
      { label: 'Page views', value: 666 },
      { label: 'Average daily users', value: 0 },
      { label: 'Table views', value: 0 },
      { label: 'Added to collections', value: 1 },
      { label: 'Bookmarked by users', value: 0 },
      { label: 'Dashboard views', value: 0 }
    ];
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => dataUsage
    });
    const response = await fetchDataUsage('datasets', '123');
    expect(response).toEqual(expected);
  });

  it('should return an error', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false
    });
    expect(fetchDataUsage('datasets', '123')).rejects.toBeInstanceOf(ApiError);
  });
});

describe('fetchRecentCollections', () => {
  it('should return a transformed response', async () => {
    const expected = [
      {
        name: 'Ians personal collection',
        url: '/collections/3d6111f8-ea21-42bc-9514-c3072caa8af0'
      },
      {
        name: 'Data Workspace feedback banner results',
        url: '/collections/4e9e91a6-b519-45f9-87a4-4e6bbedddbc2'
      },
      {
        name: 'Interactions and service deliveries for companies between 2010 and 2023',
        url: '/collections/fd135668-bebe-4270-aec3-067e525bdc50'
      }
    ];
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => recentCollections
    });
    const response = await fetchRecentCollections();
    expect(response).toEqual(expected);
  });

  it('should return an error', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false
    });
    expect(fetchRecentCollections()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('fetchRecentItems', () => {
  it('should return a transformed response', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => recentItems
    });
    const expected = [
      { name: 'Tables and Links 1', url: '/datasets/001122' },
      { name: 'Tables and Links 1', url: '/datasets/001122' },
      { name: 'Tables and Links 1', url: '/datasets/001122' },
      { name: 'Source data set 1', url: '/datasets/003344' },
      { name: 'Source data set 1', url: '/datasets/003344' }
    ];
    const response = await fetchRecentItems();
    expect(response).toEqual(expected);
  });
  it('should return an error', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false
    });
    expect(fetchRecentItems()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('fetchYourBookmarks', () => {
  it('should return a transformed response', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => yourBookmarks
    });
    const expected = [
      { name: 'Dummy bookmark 1', url: '/some-url1' },
      { name: 'Dummy bookmark 2', url: '/some-url2' },
      { name: 'Dummy bookmark 3', url: '/some-url3' },
      { name: 'Dummy bookmark 4', url: '/some-url4' },
      { name: 'Dummy bookmark 5', url: '/some-url5' }
    ];
    const response = await fetchYourBookmarks();
    expect(response).toEqual(expected);
  });
  it('should return an error', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false
    });
    expect(fetchYourBookmarks()).rejects.toBeInstanceOf(ApiError);
  });
});

describe('fetchYourRecentTools', () => {
  it('should return a transformed response', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => yourRecentTools
    });
    const expected = [
      {
        name: 'Superset',
        url: '/tools/superset/redirect'
      },
      {
        name: 'Data Explorer',
        url: '/tools/explorer/redirect'
      },
      {
        name: 'Data Explorer',
        url: '/tools/explorer/redirect'
      }
    ];
    const response = await fetchYourRecentTools();
    expect(response).toEqual(expected);
  });
  it('should return an error', () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false
    });
    expect(fetchYourRecentTools()).rejects.toBeInstanceOf(ApiError);
  });
});
