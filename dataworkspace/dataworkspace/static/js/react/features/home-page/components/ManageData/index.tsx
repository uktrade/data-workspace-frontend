import React from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import styled from 'styled-components';

import { Tile } from '../../../../components';
import { DIVIDER_COLOUR } from '../../../../constants';

export type ManagedDataProps = {
  count: string;
  managed_data_url: string | null;
};

const Divider = styled('hr')`
  color:${DIVIDER_COLOUR}
  height: 15px;
  margin-top: ${SPACING_POINTS['4']}px;
`;

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
        title={`You're the owner or manager of ${managed_data_stats.count} datasets`}
      >
        <div>
          <Link href={`${managed_data_stats.managed_data_url}`}>
            View and manage your data
          </Link>
        </div>
        <Divider></Divider>
        <StyledParagraph>
          Keeping your data up-to-date helps improve the quality of our data
          catalogue.{' '}
          <Link href="https://data-services-help.trade.gov.uk/data-workspace/add-share-and-manage-data/manage-data/">
            Learn how to maintain and managed data you're responsabile on Data
            Workspace
          </Link>
        </StyledParagraph>
      </Tile>
    )}
  </>
);

export default ManagedData;
