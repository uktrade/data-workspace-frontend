import { useEffect, useState } from 'react';

import FilesAndFolders from './components/FilesAndFolders';
import fetchS3Data from './services';
import type { AWSS3Config, File, Folder } from './types';

const YourFiles = ({ config }: Record<'config', AWSS3Config>) => {
  const prefix = config.initialPrefix
    .replace(/^\//, '')
    .replace(/([^/]$)/, '$1/');

  const [s3Files, setS3Files] = useState<File[]>([]);
  const [s3Folders, setS3Folders] = useState<Folder[]>([]);

  useEffect(() => {
    const fetchData = async () => {
      const s3Data = await fetchS3Data(prefix, config);
      setS3Files(s3Data.files);
      setS3Folders(s3Data.folders);
    };

    fetchData();
  }, []);

  return <FilesAndFolders folders={s3Folders} files={s3Files} />;
};

export default YourFiles;
