import React from 'react';

import { DataDisplay, FetchDataContainer } from '../../components';
import { fetchDataUsage } from '../../services';

const Container = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer fetchApi={() => fetchDataUsage('reference', id)}>
    {({ data }) => <DataDisplay data={data} />}
  </FetchDataContainer>
);

export default Container;
