import React from 'react';

import DataDisplay from '../../components/DataDisplay';
import FetchDataContainer from '../../components/FetchDataContainer';

const Container = ({ id }: { id: string }): React.ReactNode => (
  <FetchDataContainer id={id} dataType="datasets">
    {({ data, error, loading }) => (
      <DataDisplay
        data={data}
        error={error}
        loading={loading}
        footerNote={<a href="/">Find out more about the metrics above</a>}
      />
    )}
  </FetchDataContainer>
);

export default Container;
