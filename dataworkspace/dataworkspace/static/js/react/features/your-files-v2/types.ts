export type AWSS3Config = {
  region: string;
  rootUrl: string;
  bucketName: string;
  teamsPrefix: string;
  rootPrefix: string;
  initialPrefix: string;
  bigdataPrefix: string;
  credentialsUrl: string;
  endpointUrl: string;
  createTableUrl: string;
  teamsPrefixes: {
    prefix: string;
  }[];
  s3Path: string;
};

export type Params = {
  Bucket: string;
  Delimiter: string;
  Prefix: string;
};

export type File = {
  isSelected: boolean;
  lastModified: Date;
  name?: string;
  size?: number;
};

export type Folder = {
  name: string;
  isBigData?: boolean;
  isSelected: boolean;
  isSharedFolder?: boolean;
};

export type FilesAndFolders = {
  files: File[];
  folders: Folder[];
};

export type ActionType =
  | 'FETCH_FILES'
  | 'SAY_HELLO'
  | 'LOADING'
  | 'UPLOAD_FOLDERS_MODAL';

export type Action = { type: ActionType };

export type ActionWithPayload = {
  type: ActionType;
  payload: { files: File[]; folders: Folder[]; loading: boolean };
};
