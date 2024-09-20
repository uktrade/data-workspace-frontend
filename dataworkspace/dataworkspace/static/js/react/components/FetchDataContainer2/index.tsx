// @ts-nocheck
import React, { useEffect, useReducer, useState } from 'react';

import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { ERROR_COLOUR } from '../../constants';
import { homePageInitialState, homePageReducer } from '../../reducers';
import { ApiError } from '../../services';
import ApiProxy from '../../services/api-proxy';

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  color: ${ERROR_COLOUR};
`;

type FetchDataContainerProps = {
  endpoint: string;
  children: (data: unknown) => React.ReactNode;
};

type FetchDataContainer = ({
  endpoint,
  children
}: FetchDataContainerProps) => React.ReactNode;

const FetchDataContainer: FetchDataContainer = ({ action, children }) => {
  const [state, dispatch] = useReducer(homePageReducer, homePageInitialState);
  console.log('>>>>>>>>>', state);
  const { data, loading, error } = state;
  useEffect(() => {
    dispatch({ type: action });
  }, []);

  // useEffect(() => {
  //   async function fetchData() {
  //     try {
  //       const response = await ApiProxy.get(endpoint);
  //       setData(response);
  //     } catch (error) {
  //       if (error instanceof ApiError) {
  //         setError(`${error.response.status} ${error.response.statusText}`);
  //       } else {
  //         throw error;
  //       }
  //     }
  //     setLoading(false);
  //   }
  //   fetchData();
  // }, []);

  return (
    <LoadingBox loading={loading}>
      <>
        {error ? (
          <ErrorMessage data-testid="data-usage-error">
            Error: {error}
          </ErrorMessage>
        ) : (
          children(data as unknown)
        )}
      </>
    </LoadingBox>
  );
};

export default FetchDataContainer;
