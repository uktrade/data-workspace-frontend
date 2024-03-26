import AWS from 'aws-sdk';

import type { AWSS3Config, File, FilesAndFolders, Params } from './types';
import { fullPathToFilename, getFolderName } from './utils';

const transformS3Response = (
  contents: AWS.S3.ObjectList,
  prefixes: AWS.S3.CommonPrefix[],
  params: Params,
  config: AWSS3Config
): FilesAndFolders => {
  const files = contents
    .filter((file) => file.Key !== params.Prefix)
    .map(
      (file): File => ({
        lastModified: new Date(file.LastModified!),
        name: fullPathToFilename(file.Key!),
        size: file.Size,
        isSelected: false
      })
    )
    .sort((a, b) => {
      if (a.lastModified && b.lastModified) {
        return b.lastModified.valueOf() - a.lastModified.valueOf();
      } else {
        return -1;
      }
    });

  const sharedFolders =
    params.Prefix === config.rootPrefix
      ? config.teamsPrefixes.map((team) => ({
          name: getFolderName(team.prefix, config.rootPrefix),
          isSharedFolder: true,
          isSelected: false
        }))
      : [];

  const bigDataFolder =
    params.Prefix === config.rootPrefix
      ? [
          {
            name: getFolderName(
              config.rootPrefix + config.bigdataPrefix,
              config.rootPrefix
            ),
            isBigData: true,
            isSelected: false
          }
        ]
      : [];

  const userFolders = prefixes
    ? prefixes
        .filter(
          (folder) =>
            folder.Prefix !== `${config.rootPrefix}${config.bigdataPrefix}`
        )
        .map((folder) => ({
          name: getFolderName(folder.Prefix!, config.rootPrefix),
          isBigData: false,
          isSelected: false
        }))
    : [];

  const folders = [...bigDataFolder, ...sharedFolders, ...userFolders];
  return {
    files,
    folders
  };
};

export default transformS3Response;
