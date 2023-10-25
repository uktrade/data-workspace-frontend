import { API_BASE_URL, DATA_USAGE_KEYS } from './constants';

type DataUsageKeys = keyof typeof DATA_USAGE_KEYS;
type DataUsageValues = (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];

type DataType = 'datasets' | 'visualisation' | 'reference';

type DataUsage = Record<string, number>;

export type TransformedDataUsageResponse = {
  label: DataUsageValues;
  value: number;
};

export const transformDataUsageResponse = (
  response: DataUsage
): TransformedDataUsageResponse[] =>
  Object.keys(response).map(
    (key): TransformedDataUsageResponse => ({
      label: DATA_USAGE_KEYS[key as DataUsageKeys],
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
