export function getBreadcrumbs(rootPrefix, currentPrefix) {
  console.log("getBreadcrumbs");
  const breadcrumbs = [
    {
      prefix: rootPrefix,
      label: "home",
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
