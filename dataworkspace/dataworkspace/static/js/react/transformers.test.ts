import { dataUsage, recentCollections } from './services/mocks';
import {
  transformDataUsageResponse,
  transformRecentCollectionsResponse
} from './transformers';

describe('transformDataUsageResponse', () => {
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
    expect(transformDataUsageResponse(dataUsage)).toEqual(expected);
  });
});

describe('transformRecentCollectionsResponse', () => {
  it('should transform a recent collection response', () => {
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
    expect(transformRecentCollectionsResponse(recentCollections)).toEqual(
      expected
    );
  });
});
