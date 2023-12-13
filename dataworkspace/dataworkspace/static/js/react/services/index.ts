import { API_BASE_URL } from '../constants';
import {
  transformDataUsageResponse,
  transformRecentCollectionsResponse,
  transformRecentItemsResponse,
  transformYourBookmarksResponse
} from '../transformers';
import {
  type DataType,
  type DataUsageResponse,
  type RecentCollectionResponse,
  type RecentIemsResponse,
  type TransformedDataUsageResponse,
  type TransformedRecentCollectionResponse,
  type TransformedRecentItemsResponse,
  type TransformedYourBookmarksResponse,
  type YourBookmarksResponse} from '../types/index';

export class ApiError {
  constructor(public response: Response) {}
}

export const handleResponse = async <RawData, Result>(
  endpoint: string,
  transformer: (arg: RawData) => Result
): Promise<Result> => {
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new ApiError(response);
  }
  const data = await response.json();

  return transformer(data);
};

export const fetchDataUsage = async (dataType: DataType, id: string) => {
  return handleResponse<DataUsageResponse, TransformedDataUsageResponse>(
    `/${API_BASE_URL}/${dataType}/${id}/stats/`,
    transformDataUsageResponse
  );
};

export const fetchRecentCollections = async () => {
  return handleResponse<
    RecentCollectionResponse,
    TransformedRecentCollectionResponse
  >(
    `/${API_BASE_URL}/collections/?page_size=3`,
    transformRecentCollectionsResponse
  );
};

export const fetchRecentItems = async () => {
  return handleResponse<RecentIemsResponse, TransformedRecentItemsResponse>(
    `/${API_BASE_URL}/recent_items?page_size=5`,
    transformRecentItemsResponse
  );
};

export const fetchYourBookmarks = async () => {
  return handleResponse<YourBookmarksResponse, TransformedYourBookmarksResponse>(
    `/${API_BASE_URL}/your_bookmarks?page_size=5`,
    transformYourBookmarksResponse
  );
};
