import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR, LINK_COLOUR } from '../../../../constants';
import URLS from '../../../../urls';

const RecentItemsList = styled('ol')`
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

const RecentItemsLink = styled('a')`
  ${typography.font({ size: 19, weight: 'bold' })};
  color: ${LINK_COLOUR};
  text-decoration: none;
  display: block;
  padding: ${SPACING_POINTS['3']}px 0;
`;

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
  &:last-child {
    margin-bottom: 0;
  }
`;

export type RecentItemProps = {
  url: string;
  name: string;
};

const RecentItemsListItem: React.FC<RecentItemProps> = ({ url, name }) => (
  <li>
    <RecentItemsLink href={url}>{name}</RecentItemsLink>
  </li>
);

const RecentItems: React.FC<Record<'items', RecentItemProps[]>> = ({
  items
}) => (
  <Tile as="article" title="Your recent items">
    <StyledParagraph>
      This might be a Source dataset, Reference dataset, Data cut, or
      Visualisation.
    </StyledParagraph>
    {items?.length ? (
      <RecentItemsList>
        {items.map(({ url, name }, index) => (
          <RecentItemsListItem url={url} key={`${url}-${index}`} name={name} />
        ))}
      </RecentItemsList>
    ) : (
      <>
        <StyledParagraph>
          You have not searched anything yet. Use the{' '}
          <strong>search bar</strong> above to find data.
        </StyledParagraph>
        <StyledParagraph>
          To find out more about what catalogue items are
          <br />
          <Link
            href={
              URLS.external.dataServices.dataWorkspace
                .policiesAndStandardsDataTypes
            }
          >
            Data types on Data Workspace
          </Link>
        </StyledParagraph>
      </>
    )}
  </Tile>
);

export default RecentItems;
