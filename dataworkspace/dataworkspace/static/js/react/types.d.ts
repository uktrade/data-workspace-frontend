import { DATA_USAGE_KEYS } from './constants';

type DataUsageValues = (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];

export type TransformedDataUsageResponse = {
  label: DataUsageValues;
  value: number;
};
export type DataUsageResponse = Promise<TransformedDataUsageResponse[] | Error>;
