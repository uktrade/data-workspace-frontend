import React from 'react';

import { DataDisplay, FetchDataContainer } from '../../components';
import { fetchDataUsage } from '../../services';

const Container = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer fetchApi={() => fetchDataUsage('datasets', id)}>
    {({ data }) => <DataDisplay data={data} />}
  </FetchDataContainer>
);

export default Container;
