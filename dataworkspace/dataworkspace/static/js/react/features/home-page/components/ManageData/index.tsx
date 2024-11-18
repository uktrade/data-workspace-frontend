import React from 'react';

import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import { SectionBreak } from 'govuk-react';
import styled from 'styled-components';

import { Tile } from '../../../../components';

export type ManagedDataProps = {
  count: string;
  managed_data_url: string;
};

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

const ManagedData: React.FC<Record<'managed_data_stats', ManagedDataProps>> = ({
  managed_data_stats
}) => (
  <>
    {managed_data_stats && (
      <Tile
        as="article"
        title={`You're the owner or manager of ${managed_data_stats.count} dataset${Number(managed_data_stats.count) > 1 ? 's' : ''}`}
      >
        <div>
          <Link href={`${managed_data_stats.managed_data_url}`}>
            View and manage your data
          </Link>
        </div>
        <SectionBreak level="MEDIUM" visible></SectionBreak>
        <StyledParagraph>
          Keeping your data up-to-date helps improve the quality of our data
          catalogue.{' '}
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/add-share-and-manage-data/manage-data/">
            Learn how to maintain and manage data you're responsible for on Data
            Workspace
          </Link>
        </StyledParagraph>
      </Tile>
    )}
  </>
);

export default ManagedData;
