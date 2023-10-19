import { API_BASE_URL, DATA_USAGE_KEYS } from './constants';

type DataUsageKeys = keyof typeof DATA_USAGE_KEYS;

type DataUsage = Record<string, number>;

type TransformedDataUsageResponse = {
  title: string;
  value: number;
};

type DataType = 'datasets' | 'visualisation' | 'reference';

export const transformDataUsageResponse = (
  response: DataUsage
): TransformedDataUsageResponse[] =>
  Object.keys(response).map(
    (key): TransformedDataUsageResponse => ({
      title: DATA_USAGE_KEYS[key as DataUsageKeys],
      value: response[key] as number
    })
  );

export const fetchDataUsage = async (dataType: DataType, id: string) => {
  const response = await fetch(`/${API_BASE_URL}/${dataType}/${id}/stats/`);
  const dataUsage = await response.json();
  return transformDataUsageResponse(dataUsage);
};
