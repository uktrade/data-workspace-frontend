import React, { useEffect, useState } from 'react';

import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { ERROR_COLOUR } from '../../constants';
import { fetchDataUsage } from '../../services';
import { DataType } from '../../services';

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  color: ${ERROR_COLOUR};
`;

type FetchDataContainerProps = {
  id: string;
  dataType: DataType;
  children: ({
    data
  }: {
    data: { label: string; value: number }[];
  }) => React.ReactNode;
};

const FetchDataContainer = ({
  id,
  dataType,
  children
}: FetchDataContainerProps) => {
  const [data, setData] = useState<{ label: string; value: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<null | string>(null);

  useEffect(() => {
    async function fetchData() {
      const response = await fetchDataUsage(dataType, id);
      response instanceof Error
        ? setError(response.message)
        : setData(response);
      setLoading(false);
    }
    fetchData();
  }, []);

  return (
    <LoadingBox loading={loading}>
      <>
        {error ? (
          <ErrorMessage data-testid="data-usage-error">
            Error: {error}
          </ErrorMessage>
        ) : (
          children({ data })
        )}
      </>
    </LoadingBox>
  );
};

export default FetchDataContainer;
