import React from 'react';

import { DataDisplay, FetchDataContainer } from '../../components';
import { fetchDataUsage } from '../../services';

const Container = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer fetchApi={() => fetchDataUsage('visualisation', id)}>
    {({ data }) => (
      <DataDisplay
        data={data}
        footerNote={<a href="/">Find out more about the metrics above</a>}
      />
    )}
  </FetchDataContainer>
);

export default Container;
