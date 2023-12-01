import React from 'react';

import { DataDisplay, FetchDataContainer } from '../../components';
import { fetchDataUsage } from '../../services';

const SourceDataset = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer fetchApi={() => fetchDataUsage('datasets', id)}>
    {(data) => (
      <DataDisplay
        data={data}
        subTitle="The data below has been captured since this catalogue item was initially published."
      />
    )}
  </FetchDataContainer>
);

export default SourceDataset;
