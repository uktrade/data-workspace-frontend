// @ts-nocheck

import { SPACING_POINTS } from '@govuk-react/constants';
import styled from 'styled-components';

import { InnerContainer } from '../../components';
import { GREY_4 } from '../../constants';
import { HomePageProvider } from '../../context/provider';
import SupportYou from '../support/Support';
import Widgets from './components/Widgets';

const SupportSection = styled('section')`
  padding: ${SPACING_POINTS['6']}px 0 ${SPACING_POINTS['9']}px 0;
`;

const GreyStripe = styled('div')`
  padding: ${SPACING_POINTS['6']}px 0 ${SPACING_POINTS['8']}px 0;
  background-color: ${GREY_4};
`;

const HomePage = ({ csrf_token }) => {
  return (
    <HomePageProvider>
      <main role="main" id="main-content">
        <GreyStripe id="moo">
          <InnerContainer>
            <Widgets token={csrf_token} />
          </InnerContainer>
        </GreyStripe>
        <SupportSection>
          <InnerContainer>
            <SupportYou />
          </InnerContainer>
        </SupportSection>
      </main>
    </HomePageProvider>
  );
};

export default HomePage;
