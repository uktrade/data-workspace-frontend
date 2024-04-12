import type { ActionWithPayload, File, Folder } from './types';

export const state = {
  loading: false,
  files: [],
  folders: []
};

export const fetchFilesReducer = (
  state: {
    loading: boolean;
    files: File[];
    folders: Folder[];
  },
  action: ActionWithPayload
) => {
  switch (action.type) {
    case 'LOADING':
      return {
        ...state,
        loading: action.payload.loading
      };
    case 'FETCH_FILES':
      return {
        ...state,
        files: action?.payload?.files,
        folders: action?.payload?.folders,
        loading: action.payload.loading
      };
    default:
      return state;
  }
};
