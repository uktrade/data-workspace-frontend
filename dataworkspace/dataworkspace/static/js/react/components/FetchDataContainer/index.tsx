import React, { useEffect, useState } from 'react';

import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { ERROR_COLOUR } from '../../constants';
import { DataUsageResponse, TransformedDataUsageResponse } from '../../types';

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  color: ${ERROR_COLOUR};
`;

type FetchDataContainerProps = {
  fetchApi: () => DataUsageResponse;
  children: ({
    data
  }: {
    data: TransformedDataUsageResponse[];
  }) => React.ReactNode;
};

const FetchDataContainer = ({
  fetchApi,
  children
}: FetchDataContainerProps) => {
  const [data, setData] = useState<TransformedDataUsageResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<null | string>(null);

  useEffect(() => {
    async function fetchData() {
      const response = await fetchApi();
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
