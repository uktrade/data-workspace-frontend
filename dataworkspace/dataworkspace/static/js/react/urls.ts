const dataServicesHelp = 'https://data-services-help.trade.gov.uk';

const URLS = {
  external: {
    dataServices: {
      dataWorkspace: {
        collections: `${dataServicesHelp}/data-workspace/how-to/start-using-data-workspace/collections/`
      }
    }
  },
  collections: {
    base: '/collections',
    create: '/collections/create'
  }
} as const;

export default URLS;
