import { API_BASE_URL, DATA_USAGE_KEYS } from './constants';
import {
  DataType,
  DataUsageKeys,
  TransformedDataUsageResponse
} from './types/dataUsage.types';

export const transformDataUsageResponse = (
  response: Record<string, number>
): TransformedDataUsageResponse[] =>
  Object.keys(response).map(
    (key): TransformedDataUsageResponse => ({
      label: DATA_USAGE_KEYS[key as DataUsageKeys],
      value: Math.round(response[key] * 1000) / 1000
    })
  );

export const fetchDataUsage = async (
  dataType: DataType,
  id: string
): Promise<TransformedDataUsageResponse[] | Error> => {
  try {
    const response = await fetch(`/${API_BASE_URL}/${dataType}/${id}/stats/`);
    const data = await response.json();
    if (!response.ok) {
      const errorMessage = `${response.status} ${response.statusText}`;
      throw new Error(errorMessage);
    } else {
      return transformDataUsageResponse(data);
    }
  } catch (error: unknown) {
    return error instanceof Error
      ? error
      : new Error('Oops! Something went wrong!');
  }
};
