import { TransformedDataUsageResponse } from './dataUsage.types';

type Responses = TransformedDataUsageResponse[];

export type APIResponse = Promise<Responses | Error>;
