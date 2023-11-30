import { DATA_USAGE_KEYS } from './constants';
import type {
  DataUsageKeys,
  DataUsageResponse,
  RecentCollectionResponse,
  TransformedDataUsageResponse,
  TransformedRecentCollectionResponse
} from './types/';

export const transformDataUsageResponse = (
  response: DataUsageResponse
): TransformedDataUsageResponse =>
  Object.keys(response).map((key) => ({
    label: DATA_USAGE_KEYS[key as DataUsageKeys],
    value: Math.round(response[key as keyof unknown] * 1000) / 1000
  }));

export const transformRecentCollectionsResponse = (
  response: RecentCollectionResponse
): TransformedRecentCollectionResponse =>
  response.results.map(({ name, collection_url }) => ({
    title: name,
    url: collection_url
  }));
