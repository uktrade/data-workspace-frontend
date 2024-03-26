import type { FilesAndFolders } from '../../types';

const FilesAndFolders = ({ files, folders }: FilesAndFolders) => (
  <ul>
    {folders &&
      folders.map((folder) => <li key={folder.name}>{folder.name}</li>)}
    {files && files.map((file) => <li key={file.name}>{file.name}</li>)}
  </ul>
);

export default FilesAndFolders;
