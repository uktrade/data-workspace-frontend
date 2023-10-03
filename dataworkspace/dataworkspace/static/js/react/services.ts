const mockOne = [
  {
    title: 'Page views',
    value: '4,200'
  },
  {
    title: 'Table Queried by users',
    value: '1545'
  },
  {
    title: 'Table Views',
    value: '2150'
  },
  {
    title: 'Added to collections',
    value: '0'
  },
  {
    title: 'Bookmarked by users',
    value: '1556'
  }
];

const mockTwo = [
  {
    title: 'Page views',
    value: '4,200'
  },
  {
    title: 'Added to Collections',
    value: '42'
  },
  {
    title: 'Dashboard Views',
    value: '14,500'
  },
  {
    title: 'Bookmarked by users',
    value: '1,545'
  }
];

export const getDataCut = async () => {
  await new Promise((resolve) => setTimeout(resolve, 30000));
  return mockOne;
};

export const getSourceData = async () => {
  await new Promise((resolve) => setTimeout(resolve, 3000));
  return mockOne;
};

export const getRefData = async () => {
  await new Promise((resolve) => setTimeout(resolve, 3000));
  return mockOne;
};

export const getVisualisationData = async () => {
  await new Promise((resolve) => setTimeout(resolve, 3000));
  return mockTwo;
};
