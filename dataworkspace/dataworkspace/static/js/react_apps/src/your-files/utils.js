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
