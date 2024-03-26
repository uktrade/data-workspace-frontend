import type { AWSS3Config, Params } from '../types';

export const config: AWSS3Config = {
  region: 'eu-west-2',
  rootUrl: '/files/',
  bucketName: 'notebooks.dataworkspace.local',
  teamsPrefix: 'teams/',
  rootPrefix: 'user/federated/1234/',
  initialPrefix: 'user/federated/1234/',
  bigdataPrefix: 'bigdata/',
  credentialsUrl: '/api/v1/aws_credentials',
  endpointUrl: 'http://data-workspace-localstack:4566',
  createTableUrl: '/files/create-table/confirm',
  teamsPrefixes: [],
  s3Path: ''
};

export const params: Params = {
  Bucket: 'notebooks.dataworkspace.local',
  Prefix: 'user/federated/1234/',
  Delimiter: '/'
};
