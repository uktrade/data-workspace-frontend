// @ts-nocheck
import { useEffect } from 'react';

import { UPLOAD_FOLDERS_MODAL } from './actions';
import FilesAndFolders from './components/FilesAndFolders';
import { useReducerWithThunk } from './hooks';
import { fetchFilesReducer, state as yourFilesState } from './reducer';
import { fetchDataAction } from './thunks';
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
          dispatch({ type: UPLOAD_FOLDERS_MODAL });
        }}
      >
        Upload folders
      </button>

      <FilesAndFolders folders={state.files} files={state.folders} />
      <pre>{JSON.stringify(state, null, 2)}</pre>
    </>
  );
};

export default YourFiles;
