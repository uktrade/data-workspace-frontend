import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR, LINK_COLOUR } from '../../../../constants';
import URLS from '../../../../urls';
import BookmarkIcon from '../../icons/BookmarkIcon';

const YourBookmarksList = styled('ol')`
  list-style: none;
  padding: 0;
  margin: 0 0 15px;
  li {
    border-bottom: 1px solid ${DIVIDER_COLOUR};
    &:first-child a {
      padding-top: 5px;
    }
    &:last-child {
      margin-bottom: 20px;
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
  margin-right: 8px;
`;

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};

  &:last-child {
    margin-bottom: 0;
  }
`;

export type YourBookmarksProps = {
  name: string;
  url: string;
};

const YourBookmarkListItem: React.FC<YourBookmarksProps> = ({ name, url }) => (
  <li>
    <YourBookmarksLink href={url}>
      <BookmarkIconWrapper>
        <BookmarkIcon isBookmarked={true} />
      </BookmarkIconWrapper>
      {name}
    </YourBookmarksLink>
  </li>
);

const YourBookmarks: React.FC<Record<'bookmarks', YourBookmarksProps[]>> = ({
  bookmarks
}) => (
  <Tile as="article" title="Your bookmarks" dataTest="your-bookmarks">
    {bookmarks?.length ? (
      <>
        <StyledParagraph>
          Bookmarks are easy ways for you to access data you regularly use
          quicker.
        </StyledParagraph>
        <YourBookmarksList>
          {bookmarks.map(({ url, name }, index) => (
            <YourBookmarkListItem
              url={url}
              key={`${url}-${index}`}
              name={name}
            />
          ))}
        </YourBookmarksList>
        <Link href={URLS.collections.filtered.bookmarked}>
          View all bookmarks
        </Link>
      </>
    ) : (
      <>
        <StyledParagraph>
          Bookmarks help you get the data you regularly use.
        </StyledParagraph>
        <StyledParagraph>
          You do not have any bookmarks yet. When searching for data, select the
          bookmark icon to bookmark data.
        </StyledParagraph>
      </>
    )}
  </Tile>
);

export default YourBookmarks;
