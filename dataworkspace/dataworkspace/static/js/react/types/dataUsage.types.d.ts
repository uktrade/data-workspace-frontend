import { DATA_USAGE_KEYS } from '../constants';

export type DataUsageKeys = keyof typeof DATA_USAGE_KEYS;
export type DataUsageValues =
  (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];

export type DataType = 'datasets' | 'visualisation' | 'reference';

export type TransformedDataUsageResponse = {
  label: (typeof DATA_USAGE_KEYS)[keyof typeof DATA_USAGE_KEYS];
  value: number;
};
