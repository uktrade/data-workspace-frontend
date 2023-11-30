import React, { useEffect, useState } from 'react';

import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { ERROR_COLOUR } from '../../constants';
import { ApiError } from '../../services';

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  color: ${ERROR_COLOUR};
`;

type FetchDataContainerProps<Result> = {
  fetchApi: () => Promise<Result>;
  children: (data: Result) => React.ReactNode;
};

type FetchDataContainer = <Result>({
  fetchApi,
  children
}: FetchDataContainerProps<Result>) => React.ReactNode;

const FetchDataContainer: FetchDataContainer = ({ fetchApi, children }) => {
  type ApiReturn = ReturnType<typeof fetchApi>;
  type Result = Awaited<ApiReturn>;
  const [data, setData] = useState<unknown>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<null | string>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const response = await fetchApi();
        setData(response);
      } catch (error) {
        if (error instanceof ApiError) {
          setError(`${error.response.status} ${error.response.statusText}`);
        } else {
          throw error;
        }
      }
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
          children(data as Result)
        )}
      </>
    </LoadingBox>
  );
};

export default FetchDataContainer;
