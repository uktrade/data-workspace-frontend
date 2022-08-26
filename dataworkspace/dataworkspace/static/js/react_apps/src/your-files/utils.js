const ROOT_FOLDER_NAME = "home";
export function getBreadcrumbs(rootPrefix, currentPrefix) {
  const breadcrumbs = [
    {
      prefix: rootPrefix,
      label: ROOT_FOLDER_NAME,
    },
  ];

  const labels = currentPrefix.substring(rootPrefix.length).split("/");

  let prefix = rootPrefix;
  for (let i = 0; i < labels.length - 1; i++) {
    prefix += labels[i] + "/";
    breadcrumbs.push({
      prefix: prefix,
      label: labels[i],
    });
  }

  return breadcrumbs;
}

export function bytesToSize(bytes) {
  const sizes = ["bytes", "KB", "MB", "GB", "TB"];
  if (bytes === 0) return "0 bytes";
  const ii = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10);
  return `${Math.round(bytes / 1024 ** ii, 2)} ${sizes[ii]}`;
}

// Convert cars/vw/golf.png to golf.png
export function fullPathToFilename(path) {
  return path.replace(/^.*[\\/]/, "");
}

// Convert cars/vw/ to vw/
export function prefixToFolder(prefix) {
  if (!prefix) return "";
  const parts = prefix.split("/");
  return `${parts[parts.length - 2]}/`;
}

export function getFolderName(prefix, rootPrefix) {
  if (!prefix || !rootPrefix) return "";
  const folder = prefix.substring(rootPrefix.length);
  if (!folder) return `${ROOT_FOLDER_NAME}/`;
  return prefixToFolder(folder);
}

export function objEntries(obj) {
    var ownProps = Object.keys(obj);
    var i = ownProps.length;
    var resArray = new Array(i);
    while (i--) resArray[i] = [ownProps[i], obj[ownProps[i]]];
    return resArray;
}
