export const dataUsage = {
  page_views: 666,
  table_queries: '0.00',
  table_views: 0,
  collection_count: 1,
  bookmark_count: 0,
  dashboard_views: 0
};

export const recentCollections = {
  results: [
    {
      name: 'Ians personal collection',
      datasets: [
        {
          id: '435c4228-c70b-44b9-ac18-09d31540a0de',
          name: 'Ians source data set'
        }
      ],
      visualisation_catalogue_items: [],
      collection_url: '/collections/3d6111f8-ea21-42bc-9514-c3072caa8af0'
    },
    {
      name: 'Data Workspace feedback banner results',
      datasets: [
        {
          id: 'be7a9dfb-dd3e-4412-9047-6b767076b597',
          name: 'Ians reference data set'
        },
        {
          id: '435c4228-c70b-44b9-ac18-09d31540a0cb',
          name: 'Ians data cut - Tables and Links'
        }
      ],
      visualisation_catalogue_items: [],
      collection_url: '/collections/4e9e91a6-b519-45f9-87a4-4e6bbedddbc2'
    },
    {
      name: 'Interactions and service deliveries for companies between 2010 and 2023',
      datasets: [],
      visualisation_catalogue_items: [],
      collection_url: '/collections/fd135668-bebe-4270-aec3-067e525bdc50'
    }
  ]
};

export const recentItems = {
  count: 5,
  next: null,
  previous: null,
  results: [
    {
      id: 9,
      timestamp: '2023-12-01T12:21:36.555002Z',
      event_type: 'Dataset view',
      user_id: 1,
      related_object: null,
      extra: {
        path: '/datasets/001122',
        reference_dataset_version: '2023-12-01'
      }
    },
    {
      id: 8,
      timestamp: '2023-12-01T12:21:36.555002Z',
      event_type: 'Dataset view',
      user_id: 1,
      related_object: {
        id: '001122',
        type: 'Data cut',
        name: 'Tables and Links 1'
      },
      extra: {
        path: '/datasets/001122',
        reference_dataset_version: '2023-12-01'
      }
    },
    {
      id: 7,
      timestamp: '2023-12-01T12:05:11.070687Z',
      event_type: 'Dataset view',
      user_id: 1,
      related_object: {
        id: '001122',
        type: 'Data cut',
        name: 'Tables and Links 1'
      },
      extra: {
        path: '/datasets/001122',
        reference_dataset_version: '2023-12-01'
      }
    },
    {
      id: 6,
      timestamp: '2023-12-01T12:04:32.777435Z',
      event_type: 'Dataset view',
      user_id: 1,
      related_object: {
        id: '001122',
        type: 'Data cut',
        name: 'Tables and Links 1'
      },
      extra: {
        path: '/datasets/001122',
        reference_dataset_version: '2023-12-01'
      }
    },
    {
      id: 4,
      timestamp: '2023-12-01T12:01:05.727580Z',
      event_type: 'Dataset view',
      user_id: 1,
      related_object: {
        id: '003344',
        type: 'Source dataset',
        name: 'Source data set 1'
      },
      extra: {
        path: '/datasets/003344',
        reference_dataset_version: '2023-12-01'
      }
    },
    {
      id: 1,
      timestamp: '2023-12-01T12:00:43.643389Z',
      event_type: 'Dataset view',
      user_id: 1,
      related_object: {
        id: '003344',
        type: 'Source dataset',
        name: 'Source data set 1'
      },
      extra: {
        path: '/datasets/003344',
        reference_dataset_version: '2023-12-01'
      }
    }
  ]
};

export const yourBookmarks = {
  results: [
    {
      name: 'Dummy bookmark 1',
      url: '/some-url1'
    },
    {
      name: 'Dummy bookmark 2',
      url: '/some-url2'
    },
    {
      name: 'Dummy bookmark 3',
      url: '/some-url3'
    },
    {
      name: 'Dummy bookmark 4',
      url: '/some-url4'
    },
    {
      name: 'Dummy bookmark 5',
      url: '/some-url5'
    }
  ]
};

export const yourRecentTools = {
  count: 5,
  next: null,
  previous: null,
  results: [
    {
      id: 140,
      timestamp: '2023-12-12T17:24:58.125084Z',
      extra: { tool: 'Superset' },
      tool_url: '/tools/superset/redirect'
    },
    {
      id: 139,
      timestamp: '2023-12-12T17:24:41.992511Z',
      extra: { tool: 'Data Explorer' },
      tool_url: '/tools/explorer/redirect'
    },
    {
      id: 138,
      timestamp: '2023-12-11T13:46:03.340096Z',
      extra: { tool: 'Data Explorer' },
      tool_url: '/tools/explorer/redirect'
    }
  ]
};
