import AWS from 'aws-sdk';

import { config } from './fixtures/config';
import fetchS3Data from './services';

const prefix = config.initialPrefix
  .replace(/^\//, '')
  .replace(/([^/]$)/, '$1/');

jest.mock('aws-sdk');

describe('fetchS3Data', () => {
  it('should return files and folders', async () => {
    // @ts-ignore
    AWS.S3.mockImplementation(() => ({
      listObjectsV2: () => ({
        promise: () => ({
          IsTruncated: false,
          Contents: [
            {
              Key: 'user/federated/4f54003249593a7eccd6e9aa732d14b9eb53d8f57829020da8b2cdad6f35bbc2/test.txt',
              LastModified: '2024-03-25T12:01:49.000Z',
              ETag: '"d41d8cd98f00b204e9800998ecf8427e"',
              ChecksumAlgorithm: [],
              Size: 0,
              StorageClass: 'STANDARD'
            }
          ],
          Name: 'notebooks.dataworkspace.local',
          Prefix:
            'user/federated/4f54003249593a7eccd6e9aa732d14b9eb53d8f57829020da8b2cdad6f35bbc2/',
          Delimiter: '/',
          MaxKeys: 1000,
          CommonPrefixes: [],
          KeyCount: 1
        })
      })
    }));
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => ''
    });
    expect(await fetchS3Data(prefix, config)).toEqual({
      files: [
        {
          isSelected: false,
          lastModified: new Date('2024-03-25T12:01:49.000Z'),
          name: 'test.txt',
          size: 0
        }
      ],
      folders: [{ isBigData: true, isSelected: false, name: 'bigdata/' }]
    });
  });
  it('should log an error', async () => {
    // @ts-ignore
    AWS.S3.mockImplementation(() => ({
      listObjectsV2: () => ({
        promise: () => Promise.reject('something went wrong')
      })
    }));
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      statusText: 'status text message',
      json: async () => ''
    });

    const error = jest.spyOn(console, 'error');
    await fetchS3Data(prefix, config);
    expect(error).toHaveBeenCalledWith('something went wrong');
  });
});
