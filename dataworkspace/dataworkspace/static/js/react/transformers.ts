import { DATA_USAGE_KEYS } from './constants';
import type {
  DataUsageKeys,
  DataUsageResponse,
  RecentCollectionResponse,
  RecentIemsResponse,
  TransformedDataUsageResponse,
  TransformedRecentCollectionResponse,
  TransformedRecentItemsResponse,
  TransformedYourBookmarksResponse,
  YourBookmarksResponse
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

export const transformRecentItemsResponse = (
  response: RecentIemsResponse
): TransformedRecentItemsResponse =>
  response.results.map(({ related_object, extra }) => ({
    title: related_object.name,
    url: extra.path
  }));

export const transformYourBookmarksResponse = (
  response: YourBookmarksResponse
): TransformedYourBookmarksResponse =>
  response.results.map(({ name, url }) => ({
    name: name,
    url: url
  }));
