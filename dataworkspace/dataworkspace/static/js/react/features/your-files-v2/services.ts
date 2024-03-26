import AWS from 'aws-sdk';

import transformS3Response from './transformer';
import type { AWSS3Config } from './types';

const fetchS3Data = async (prefix: string, config: AWSS3Config) => {
  try {
    const credentialsResponse = await (
      await fetch(config.credentialsUrl)
    ).json();
    const awsConfig = {
      credentials: {
        credentialsUrl: config.credentialsUrl,
        expiration: Date.parse(credentialsResponse.Expiration),
        accessKeyId: credentialsResponse.AccessKeyId,
        secretAccessKey: credentialsResponse.SecretAccessKey,
        sessionToken: credentialsResponse.SessionToken
      },
      region: config.region,
      s3ForcePathStyle: true,
      ...(config.endpointUrl ? { endpoint: config.endpointUrl } : {}),
      httpOptions: {
        timeout: 10 * 60 * 60 * 1000
      }
    };

    const s3 = new AWS.S3(awsConfig);

    const params = {
      Bucket: config.bucketName,
      Prefix: prefix,
      Delimiter: '/'
    };

    const response = await s3.listObjectsV2(params).promise();

    const contents = response.Contents || [];
    const prefixes = response.CommonPrefixes || [];

    const { files, folders } = transformS3Response(
      contents,
      prefixes,
      params,
      config
    );
    return {
      files,
      folders
    };
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error(error);
  }
};

export default fetchS3Data;
