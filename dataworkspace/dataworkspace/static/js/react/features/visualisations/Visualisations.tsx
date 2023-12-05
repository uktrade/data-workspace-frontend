import React from 'react';

import { DataDisplay, FetchDataContainer } from '../../components';
import { fetchDataUsage } from '../../services';

const Visualisations = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer fetchApi={() => fetchDataUsage('visualisation', id)}>
    {(data) => (
      <DataDisplay
        data={data}
        subTitle="The data below has been captured since this catalogue item was initially published."
        historyUrl={`/datasets/${id}/visualisation-usage-history`}
        secondary
      />
    )}
  </FetchDataContainer>
);

export default Visualisations;
