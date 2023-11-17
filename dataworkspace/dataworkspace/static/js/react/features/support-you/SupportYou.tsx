import React from 'react';

import { MEDIA_QUERIES, SPACING_POINTS } from '@govuk-react/constants';
import { H2 } from 'govuk-react';
import styled from 'styled-components';

import GetHelp from '../../components/GetHelp';
import OtherSupport from '../../components/OtherSupport';
import { WHITE } from '../../constants';

const SupportYouContainer = styled('div')`
  background-color: ${WHITE};
`;

const TilesContainer = styled('div')`
  display: grid;
  grid-template-columns: 1fr;
  grid-gap: ${SPACING_POINTS[3]}px;
  ${MEDIA_QUERIES.TABLET} {
    grid-template-columns: repeat(2, 1fr);
    grid-gap: ${SPACING_POINTS[6]}px;
  }
`;

const SupportYou: React.FC = () => {
  return (
    <SupportYouContainer>
      <H2>How can we support you?</H2>
      <TilesContainer>
        <GetHelp />
        <OtherSupport />
      </TilesContainer>
    </SupportYouContainer>
  );
};

export default SupportYou;
