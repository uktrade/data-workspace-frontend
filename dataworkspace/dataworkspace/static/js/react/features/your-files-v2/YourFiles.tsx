// @ts-nocheck
import { useEffect } from 'react';

import FilesAndFolders from './components/FilesAndFolders';
import { useReducerWithThunk } from './hooks';
import { fetchFilesReducer, state as yourFilesState } from './reducer';
import { fetchAMessage, fetchDataAction } from './thunks';
import type { AWSS3Config } from './types';

const YourFiles = ({ config }: Record<'config', AWSS3Config>) => {
  const prefix = config.initialPrefix
    .replace(/^\//, '')
    .replace(/([^/]$)/, '$1/');

  const [state, dispatch] = useReducerWithThunk(
    fetchFilesReducer,
    yourFilesState
  );

  useEffect(() => {
    dispatch(fetchDataAction(prefix, config));
  }, []);

  return state.loading ? (
    <>Loading....</>
  ) : (
    <>
      <button
        onClick={() => {
          dispatch(fetchDataAction(prefix, config));
        }}
      >
        Reload
      </button>
      <FilesAndFolders folders={state.files} files={state.folders} />
    </>
  );
};

export default YourFiles;
