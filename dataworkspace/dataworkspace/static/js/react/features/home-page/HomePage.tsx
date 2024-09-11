import { MEDIA_QUERIES, SPACING_POINTS } from '@govuk-react/constants';
import styled from 'styled-components';

import { FetchDataContainer, InnerContainer } from '../../components';
import { GREY_4 } from '../../constants';
import {
  fetchProfileHomepageSettings,
  fetchRecentCollections,
  fetchRecentItems,
  fetchYourBookmarks,
  fetchYourRecentTools
} from '../../services';
import SupportYou from '../support/Support';
import RecentCollections from './components/RecentCollections';
import RecentItems from './components/RecentItems';
import RecentTools from './components/RecentTools';
import YourBookmarks from './components/YourBookmarks';

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

const HomePage = () => (
  <main role="main" id="main-content">
    <YourSection>
      <InnerContainer>
        <div>
          <FetchDataContainer fetchApi={() => fetchProfileHomepageSettings()}>
            {(data) => <>{console.log(data)}</>}
          </FetchDataContainer>
          <FetchDataContainer fetchApi={() => fetchRecentItems()}>
            {(data) => <RecentItems items={data} />}
          </FetchDataContainer>
          <FetchDataContainer fetchApi={() => fetchYourRecentTools()}>
            {(data) => <RecentTools tools={data} />}
          </FetchDataContainer>
        </div>
        <div>
          <FetchDataContainer fetchApi={() => fetchRecentCollections()}>
            {(data) => <RecentCollections collections={data} />}
          </FetchDataContainer>
          <FetchDataContainer fetchApi={() => fetchYourBookmarks()}>
            {(data) => <YourBookmarks bookmarks={data} />}
          </FetchDataContainer>
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

export default HomePage;
