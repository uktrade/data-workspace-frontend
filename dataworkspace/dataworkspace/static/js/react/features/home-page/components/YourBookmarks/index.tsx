import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR, LINK_COLOUR } from '../../../../constants';

const YourBookmarksList = styled('ol')`
  list-style: none;
  padding: 0;
  margin: 0;
  li {
    border-bottom: 1px solid ${DIVIDER_COLOUR};
    &:first-child a {
      padding-top: 5px;
    }
  }
`;

const YourBookmarksLink = styled('a')`
  ${typography.font({ size: 19, weight: 'bold' })};
  color: ${LINK_COLOUR};
  text-decoration: none;
  display: block;
  padding: ${SPACING_POINTS['3']}px 0;
`;

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

export type YourBookmarkProps = {
    name: string;
    url: string;
};

const YourBookmarkListItem: React.FC<YourBookmarkProps> = ({ name, url }) => (
    <li>
        <YourBookmarksLink href={url}>{name}</YourBookmarksLink>
    </li>
);

const YourBookmarks: React.FC<Record<'bookmarks', YourBookmarkProps[]>> = ({
    bookmarks
}) => (
    <Tile title="Your bookmarks">
        <StyledParagraph>
            Bookmarks are easy ways for you to access 
            data you regularly use quicker.
        </StyledParagraph>
        {bookmarks?.length ? (
            <>
                <YourBookmarksList>
                    {bookmarks.slice(0, 5).map(({ url, name }, index) => (
                        <YourBookmarkListItem
                            url={url}
                            key={`${url}-${index}`}
                            name={name}
                        />
                    ))}
                </YourBookmarksList>
                <Link
                    href='#'
                >
                        View all bookmarks
                </Link>
            </>
        ) : (
            <>
                <StyledParagraph>
                    Bookmarks help you get the data you regularly use.
                </StyledParagraph>
                <StyledParagraph>
                You do not have any bookmarks yet. Select the bookmark
                 icon to bookmark data.
                </StyledParagraph>
                <StyledParagraph>
                    For more information on bookmarking data
                    <br />
                    <Link
                        href='#'
                    >
                        How to bookmark data on Data Workspace
                    </Link>
                </StyledParagraph>
            </>
        )}
    </Tile>
);

export default YourBookmarks;