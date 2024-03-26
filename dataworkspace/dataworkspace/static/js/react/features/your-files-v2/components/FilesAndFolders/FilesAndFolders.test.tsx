import { render } from '@testing-library/react';

import type { File, Folder } from '../../types';
import FilesAndFolders from '.';

const folders: Folder[] = [
  { name: '/bigdata/', isSelected: false },
  { name: '/myFolder/', isSelected: false }
];

const files: File[] = [
  { name: 'test1.txt', isSelected: false, lastModified: new Date() },
  { name: 'test2.txt', isSelected: false, lastModified: new Date() }
];

describe('FilesAndFolders', () => {
  it('should display files', () => {
    const { getByText, queryByText } = render(
      <FilesAndFolders folders={[]} files={files} />
    );
    expect(queryByText('/bigdata/')).not.toBeInTheDocument();
    expect(queryByText('/myFolder/')).not.toBeInTheDocument();
    expect(getByText('test1.txt')).toBeInTheDocument();
    expect(getByText('test2.txt')).toBeInTheDocument();
  });

  it('should display folders', () => {
    const { getByText, queryByText } = render(
      <FilesAndFolders folders={folders} files={[]} />
    );
    expect(getByText('/bigdata/')).toBeInTheDocument();
    expect(getByText('/myFolder/')).toBeInTheDocument();
    expect(queryByText('test1.txt')).not.toBeInTheDocument();
    expect(queryByText('test2.txt')).not.toBeInTheDocument();
  });

  it('should display files and folders', () => {
    const { getByText } = render(
      <FilesAndFolders folders={folders} files={files} />
    );
    expect(getByText('/bigdata/')).toBeInTheDocument();
    expect(getByText('/myFolder/')).toBeInTheDocument();
    expect(getByText('test1.txt')).toBeInTheDocument();
    expect(getByText('test2.txt')).toBeInTheDocument();
  });
});
