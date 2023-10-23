import { API_BASE_URL, DATA_USAGE_KEYS } from './constants';

type DataUsageKeys = keyof typeof DATA_USAGE_KEYS;
type DataUsageValues = (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];

type DataUsage = Record<string, number>;

export type TransformedDataUsageResponse = {
  title: DataUsageValues;
  value: number;
};

export type DataType = 'datasets' | 'visualisation' | 'reference';

export const transformDataUsageResponse = (
  response: DataUsage
): TransformedDataUsageResponse[] =>
  Object.keys(response).map(
    (key): TransformedDataUsageResponse => ({
      title: DATA_USAGE_KEYS[key as DataUsageKeys],
      value: response[key] as number
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
      throw new Error(response.statusText);
    } else {
      return transformDataUsageResponse(data);
    }
  } catch (error: unknown) {
    return error instanceof Error
      ? error
      : new Error('Error: something has gone wrong.');
  }
};
