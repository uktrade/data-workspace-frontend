// @ts-nocheck
import { useEffect, useReducer } from 'react';

import { MEDIA_QUERIES, SPACING_POINTS } from '@govuk-react/constants';
import styled from 'styled-components';

import { FETCH_PROFILE } from '../../actions';
import { FetchDataContainer2, InnerContainer } from '../../components';
import { GREY_4 } from '../../constants';
// import RecentCollections from './components/RecentCollections';
// import RecentItems from './components/RecentItems';
// import RecentTools from './components/RecentTools';
// import YourBookmarks from './components/YourBookmarks';
import { homePageReducer, initialState } from '../../reducers';
// import {
//   fetchHomepageTiles,
//   fetchRecentCollections,
//   fetchRecentItems,
//   fetchYourBookmarks,
//   fetchYourRecentTools
// } from '../../services';
import SupportYou from '../support/Support';

const YourSection = styled('div')`
  padding: ${SPACING_POINTS['6']}px 0 ${SPACING_POINTS['8']}px 0;
  background-color: ${GREY_4};
  > div {
    > div > div {
      margin-bottom: 15px;
    }
    ${MEDIA_QUERIES.TABLET} {
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-gap: 30px;
      > div > div {
        margin-bottom: ${SPACING_POINTS['6']}px;
        &:last-child {
          margin-bottom: 0;
        }
      }
    }
  }
`;

const SupportSection = styled('section')`
  padding: ${SPACING_POINTS['6']}px 0 ${SPACING_POINTS['9']}px 0;
`;

const HomePage = () => {
  const [state, dispatch] = useReducer(homePageReducer, initialState);

  useEffect(() => {
    dispatch({ type: 'FETCH_TILES' });
  }, []);

  return (
    <main role="main" id="main-content">
      <YourSection>
        <button onClick={() => dispatch({ type: 'FETCH_TILES' })}>
          click me
        </button>
        <InnerContainer>
          <div>
            <FetchDataContainer2 action={FETCH_PROFILE}>
              {(data) => <>{console.log(data)}</>}
            </FetchDataContainer2>
          </div>
        </InnerContainer>
      </YourSection>
      <SupportSection>
        <InnerContainer>
          <SupportYou />
        </InnerContainer>
      </SupportSection>
    </main>
  );
};

export default HomePage;
