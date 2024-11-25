import React from 'react';

import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import { SectionBreak } from 'govuk-react';
import styled from 'styled-components';

import { Tile } from '../../../../components';

export type ManagedDataProps = {
  count: number;
  managed_data_url: string;
};

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
  margin: 0;
`;

const ManagedData: React.FC<
  Record<'managed_data_stats', ManagedDataProps[]>
> = ({ managed_data_stats }) => (
  <>
    {managed_data_stats?.length > 0 && (
      <Tile
        as="article"
        contentWrapper={true}
        title={`You're the owner or manager of ${managed_data_stats[0].count} dataset${managed_data_stats[0].count > 1 ? 's' : ''}`}
      >
        <Link href={`${managed_data_stats[0].managed_data_url}`}>
          View and manage your data
        </Link>
        <SectionBreak level="MEDIUM" visible></SectionBreak>
        <StyledParagraph>
          Keeping your data up-to-date helps improve the quality of our data
          catalogue.{' '}
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/how-to/data-owner-basics/managing-data-key-tasks-and-responsibilities">
            Learn how to maintain and manage data you're responsible for on Data
            Workspace
          </Link>
        </StyledParagraph>
      </Tile>
    )}
  </>
);

export default ManagedData;
