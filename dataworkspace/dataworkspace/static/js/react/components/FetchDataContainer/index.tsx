// @ts-nocheck
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
  renderIfDataEmpty?: boolean;
  children: (data: Result) => React.ReactNode;
};

type FetchDataContainer = <Result>({
  fetchApi,
  renderIfDataEmpty,
  children
}: FetchDataContainerProps<Result>) => React.ReactNode;

const FetchDataContainer: FetchDataContainer = ({
  fetchApi,
  renderIfDataEmpty = true,
  children
}) => {
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
  const hasData = data && (Array.isArray(data) ? data.length > 0 : true);
  return (
    <>
      {hasData || renderIfDataEmpty ? (
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
      ) : null}
    </>
  );
};

export default FetchDataContainer;
