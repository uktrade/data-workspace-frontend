export const datacutWithNoPermissions = "f66c88c3-b6de-4c18-921f-8cd409861eab";
export const datacutWithLinks = "161d4b68-4b0d-4d96-80dc-d2f9867ff515";
export const datacutWithTableAndLinks = "b603337f-0073-43ac-9dc4-05a8d5cf635d";
export const sourceWithTable = "3112a785-6bd9-4e56-bc67-10b6cccb5db7";
export const sourceWithTableNoPermissions =
  "d7094267-ddfc-40f3-a4a8-ca4f30a0992f";
export const sourceWithTableNoAccess = "7533af71-45ec-49fc-92c8-03d421af7250";

export type DataCatalogueIDType =
  | typeof datacutWithNoPermissions
  | typeof datacutWithLinks
  | typeof datacutWithTableAndLinks
  | typeof sourceWithTable
  | typeof sourceWithTableNoPermissions
  | typeof sourceWithTableNoAccess;
