import React, { ReactNode } from 'react';

import { SPACING } from '@govuk-react/constants';
import styled from 'styled-components';

import { InnerContainer } from '../../components';

const OuterContainer = styled('main')({
  paddingTop: SPACING.SCALE_5,
  paddingBottom: SPACING.SCALE_5,
  textAlign: 'center'
});

type MainProps = {
  children: ReactNode;
};

const Main: React.FC<MainProps> = ({ children, ...props }) => (
  <OuterContainer
    {...props}
    role="main"
    id="main-content"
    data-test="bodyMainContent"
  >
    <InnerContainer>{children}</InnerContainer>
  </OuterContainer>
);

export default Main;
