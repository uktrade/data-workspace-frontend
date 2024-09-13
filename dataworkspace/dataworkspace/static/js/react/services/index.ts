// @ts-nocheck
import { API_BASE_URL } from '../constants';
import {
  transformDataUsageResponse,
  transformRecentCollectionsResponse,
  transformRecentItemsResponse,
  transformRecentToolsResponse,
  transformYourBookmarksResponse
} from '../transformers';
import {
  type DataType,
  type DataUsageResponse,
  type TransformedDataUsageResponse,
  type TransformedYourBookmarksResponse,
  type TransformedYourRecentCollectionResponse,
  type TransformedYourRecentItemsResponse,
  type TransformedYourRecentToolsResponse,
  type YourBookmarksResponse,
  type YourRecentCollectionResponse,
  type YourRecentIemsResponse,
  type YourRecentToolsResponse
} from '../types/index';

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
    YourRecentCollectionResponse,
    TransformedYourRecentCollectionResponse
  >(
    `/${API_BASE_URL}/collections/?page_size=3`,
    transformRecentCollectionsResponse
  );
};

export const fetchRecentItems = async () => {
  return handleResponse<
    YourRecentIemsResponse,
    TransformedYourRecentItemsResponse
  >(`/${API_BASE_URL}/recent_items?page_size=5`, transformRecentItemsResponse);
};

export const fetchYourBookmarks = async () => {
  return handleResponse<
    YourBookmarksResponse,
    TransformedYourBookmarksResponse
  >(
    `/${API_BASE_URL}/your_bookmarks?page_size=5`,
    transformYourBookmarksResponse
  );
};

export const fetchYourRecentTools = async () => {
  return handleResponse<
    YourRecentToolsResponse,
    TransformedYourRecentToolsResponse
  >(`/${API_BASE_URL}/recent_tools?page_size=2`, transformRecentToolsResponse);
};

export const fetchHomepageTiles = async () => {
  const response = await new Promise((resolve, reject) => {
    setTimeout(() => {
      resolve({
        user_profile: {
          homepage_tiles: {
            recent_items: true,
            recent_collections: true,
            recent_tools: true,
            bookmarks: true
          }
        }
      });
    }, 1000);
  });
  return response;
};

export { patchFeedback, postFeedback } from './inline-feedback';
