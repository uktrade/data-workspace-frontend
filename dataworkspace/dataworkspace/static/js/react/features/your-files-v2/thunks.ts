import { Dispatch } from 'react';

import fetchS3Data from './services';
import type { ActionWithPayload, AWSS3Config, FilesAndFolders } from './types';

export const fetchDataAction = (prefix: string, config: AWSS3Config) => {
  return async (dispatch: Dispatch<ActionWithPayload>) => {
    dispatch({
      type: 'LOADING',
      payload: { files: [], folders: [], loading: true }
    });
    const data: FilesAndFolders | undefined = await fetchS3Data(prefix, config);
    if (data) {
      dispatch({ type: 'FETCH_FILES', payload: { ...data, loading: false } });
    }
  };
};
