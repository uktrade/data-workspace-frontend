import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR, LINK_COLOUR } from '../../../../constants';
import BookmarkIcon from '../../../../icons/BookmarkIcon';
import URLS from '../../../../urls';

const YourBookmarksList = styled('ol')`
  list-style: none;
  padding: 0;
  margin: 0 0 15px;
  li {
    border-bottom: 1px solid ${DIVIDER_COLOUR};
    &:first-child a {
      padding-top: 5px;
    }
  }
`;

const YourBookmarksLink = styled('a')`
  ${typography.font({ size: 16, weight: 'bold' })};
  color: ${LINK_COLOUR};
  text-decoration: none;
  display: flex;
  padding: ${SPACING_POINTS['3']}px 0;
`;

const BookmarkIconWrapper = styled.span`
  margin-right: 8px; /* Adjust spacing between the icon and text */
`;

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

export type YourBookmarksProps = {
    name: string;
    url: string;
};

const YourBookmarkListItem: React.FC<YourBookmarksProps> = ({ name, url }) => (
    <li>
        <YourBookmarksLink href={url}>
            <BookmarkIconWrapper>
                <BookmarkIcon /> 
            </BookmarkIconWrapper>
            {name}
        </YourBookmarksLink>
    </li>
);

const YourBookmarks: React.FC<Record<'bookmarks', YourBookmarksProps[]>> = ({
    bookmarks
}) => (
    <Tile title="Your bookmarks">
        {bookmarks?.length ? (
            <>
                <StyledParagraph>
                    Bookmarks are easy ways for you to access 
                    data you regularly use quicker.
                </StyledParagraph>
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
                        href={
                            URLS.external.dataServices.dataWorkspace
                                .policiesAndStandardsDataTypes
                        }
                    >
                        How to bookmark data on Data Workspace
                    </Link>
                </StyledParagraph>
            </>
        )}
    </Tile>
);

export default YourBookmarks;