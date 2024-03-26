import AWS from 'aws-sdk';

import { config, params } from './fixtures/config';
import transformS3Response from './transformer';

const dateString = new Date('2024-03-25T12:01:49.000Z');
const contents: AWS.S3.ObjectList = [
  {
    Key: 'user/federated/4f54003249593a7eccd6e9aa732d14b9eb53d8f57829020da8b2cdad6f35bbc2/test.txt',
    LastModified: new Date(dateString),
    ETag: '"d41d8cd98f00b204e9800998ecf8427e"',
    ChecksumAlgorithm: [],
    Size: 0,
    StorageClass: 'STANDARD'
  }
];
const prefixes: AWS.S3.CommonPrefix[] = [
  {
    Prefix: 'user/federated/1234/myFolder/'
  }
];

describe('Transformer', () => {
  describe('New users', () => {
    it('should show a BigData folder by default', () => {
      expect(transformS3Response([], [], params, config)).toEqual({
        files: [],
        folders: [{ isBigData: true, isSelected: false, name: 'bigdata/' }]
      });
    });
  });
  describe('Existing users', () => {
    it('should show folders', () => {
      expect(transformS3Response([], prefixes, params, config)).toEqual({
        files: [],
        folders: [
          { isBigData: true, isSelected: false, name: 'bigdata/' },
          { isBigData: false, isSelected: false, name: 'myFolder/' }
        ]
      });
    });
    it('should show files', () => {
      expect(transformS3Response(contents, [], params, config)).toEqual({
        files: [
          {
            isSelected: false,
            lastModified: new Date(dateString),
            name: 'test.txt',
            size: 0
          }
        ],
        folders: [{ isBigData: true, isSelected: false, name: 'bigdata/' }]
      });
    });
    it('should show folders and files', () => {
      expect(transformS3Response(contents, prefixes, params, config)).toEqual({
        files: [
          {
            isSelected: false,
            lastModified: new Date(dateString),
            name: 'test.txt',
            size: 0
          }
        ],
        folders: [
          { isBigData: true, isSelected: false, name: 'bigdata/' },
          { isBigData: false, isSelected: false, name: 'myFolder/' }
        ]
      });
    });
  });
});
