import React, { useEffect, useState } from 'react';

import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { YOUR_BOOKMARK_KEYS } from '../../constants';
import { ERROR_COLOUR } from '../../constants';

type TransformedYourBookmarksResponse = {
    label: (typeof YOUR_BOOKMARK_KEYS)[keyof typeof YOUR_BOOKMARK_KEYS];
    value: string;
};

type Responses = TransformedYourBookmarksResponse[];
type APIResponse = Promise<Responses | Error>

// 

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  color: ${ERROR_COLOUR};
`;

type FetchYourBookmarksContainerProps = {
    fetchApi: () => APIResponse;
    children: ({
      bookmarks
    }: {
      bookmarks: TransformedYourBookmarksResponse[];
    }) => React.ReactNode;
  };

const FetchYourBookmarksContainer = ({
    fetchApi,
    children
}: FetchYourBookmarksContainerProps) => {
    const [bookmarks, setBookmarks] = useState<TransformedYourBookmarksResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<null | string>(null);

    useEffect(() => {
        async function fetchYourBookmarks() {
            const response = await fetchApi();
            response instanceof Error
                ? setError(response.message)
                : setBookmarks(response);
            setLoading(false);
        }
        fetchYourBookmarks();
    });

    return (
        <LoadingBox loading={loading}>
            <>
                {error ? (
                    <ErrorMessage data-testid='bookmarks-error'>
                        Error: {error}
                    </ErrorMessage>
                ) : (
                    children({ bookmarks })
                )};
            </>
        </LoadingBox>
    );
};

export default FetchYourBookmarksContainer;
