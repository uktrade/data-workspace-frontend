const ROOT_FOLDER_NAME = 'home';
// Convert cars/vw/golf.png to golf.png
export function fullPathToFilename(path: string) {
  return path.replace(/^.*[\\/]/, '');
}

// Convert cars/vw/ to vw/
export function prefixToFolder(prefix: string) {
  if (!prefix) return '';
  const parts = prefix.split('/');
  return `${parts[parts.length - 2]}/`;
}

export function getFolderName(prefix: string, rootPrefix: string) {
  if (!prefix || !rootPrefix) return '';
  const folder = prefix.substring(rootPrefix.length);
  if (!folder) return `${ROOT_FOLDER_NAME}/`;
  return prefixToFolder(folder);
}
