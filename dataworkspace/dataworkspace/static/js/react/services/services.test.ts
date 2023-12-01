import { fetchDataUsage, fetchRecentCollections } from './';
import { dataUsage, recentCollections } from './mocks';

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
});

describe('fetchRecentCollections', () => {
  it('should return a transformed response', async () => {
    const expected = [
      {
        title: 'Ians personal collection',
        url: '/collections/3d6111f8-ea21-42bc-9514-c3072caa8af0'
      },
      {
        title: 'Data Workspace feedback banner results',
        url: '/collections/4e9e91a6-b519-45f9-87a4-4e6bbedddbc2'
      },
      {
        title:
          'Interactions and service deliveries for companies between 2010 and 2023',
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
});
