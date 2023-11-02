import React from 'react';

import { DataDisplay, FetchDataContainer } from '../../components';
import { fetchDataUsage } from '../../services';

const Container = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer fetchApi={() => fetchDataUsage('visualisation', id)}>
    {({ data }) => <DataDisplay data={data} secondary />}
  </FetchDataContainer>
);

export default Container;
