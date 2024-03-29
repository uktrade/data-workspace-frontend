import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import { H4, UnorderedList } from 'govuk-react';
import styled from 'styled-components';

import { Tile } from '../../../../components';

const StyledParagraph = styled('p')`
  margin: ${SPACING_POINTS[4]}px 0;
  ${typography.font({ size: 16 })};
`;

const LinkList = styled(UnorderedList)`
  list-style: none;
  padding: ${SPACING_POINTS[0]}px;
  margin: ${SPACING_POINTS[0]}px;
`;

const LinkListItem = styled('li')`
  margin: ${SPACING_POINTS[4]}px 0;
  ${typography.font({ size: 16 })};

  &:last-child {
    margin-bottom: 0;
  }
`;

const GetHelp: React.FC = () => {
  return (
    <Tile as="article" headerLevel={3} title="Get help">
      <StyledParagraph>
        Find documentation, guidance, standards, training and updates on the{' '}
        <Link href="https://data-services-help.trade.gov.uk/data-workspace/">
          Data Services Help Centre
        </Link>
      </StyledParagraph>
      <H4 size={'SMALL'}>Suggested articles</H4>
      <LinkList>
        <LinkListItem>
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/how-to/use-tools/">
            How to start using tools
          </Link>
        </LinkListItem>
        <LinkListItem>
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/how-to/share-and-collaborate/">
            Share and collaborate
          </Link>
        </LinkListItem>
        <LinkListItem>
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/how-to/start-using-data-workspace/">
            Getting started on Data Workspace
          </Link>
        </LinkListItem>
        <LinkListItem>
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/how-to/4-manage-your-data/">
            How to add data on Data Workspace
          </Link>
        </LinkListItem>
      </LinkList>
    </Tile>
  );
};

export default GetHelp;
