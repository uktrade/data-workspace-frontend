import { DATA_USAGE_KEYS } from '../constants';

export type DataUsageKeys = keyof typeof DATA_USAGE_KEYS;
export type DataUsageValues =
  (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];

export type DataType =
  | 'datasets'
  | 'visualisation'
  | 'reference'
  | 'collections';

export type DataUsageResponse = {
  page_views: number;
  table_queries: string;
  table_views: number;
  collection_count: number;
  bookmark_count: number;
};

export type TransformedDataUsageResponse = {
  label: (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];
  value: number;
}[];

export type RecentCollectionResponse = {
  results: {
    name: string;
    collection_url: string;
  }[];
};

export type TransformedRecentCollectionResponse = {
  title: string;
  url: string;
}[];

export type RecentIemsResponse = {
  results: {
    related_object: {
      name: string;
    };
    extra: {
      path: string;
    };
  }[];
};

export type TransformedRecentItemsResponse = {
  title: string;
  url: string;
}[];

export type YourBookmarksResponse = {
  results: {
    name: string;
    url: string;
  }[];
};

export type TransformedYourBookmarksResponse = {
  name: string;
  url: string;
}[];