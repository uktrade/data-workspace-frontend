import { API_BASE_URL } from '../constants';
import {
  transformDataUsageResponse,
  transformRecentCollectionsResponse
} from '../transformers';
import type {
  DataType,
  DataUsageResponse,
  RecentCollectionResponse,
  TransformedDataUsageResponse,
  TransformedRecentCollectionResponse
} from '../types/index';

export class ApiError {
  constructor(public response: Response) {}
}

export async function handleResponse<RawData, Result>(
  endpoint: string,
  transformer: (arg: RawData) => Result
): Promise<Result> {
  const response = await fetch(endpoint);
  if (!response.ok) {
    throw new ApiError(response);
  }
  const data = await response.json();

  return transformer(data);
}

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
