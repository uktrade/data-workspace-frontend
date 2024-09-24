// @ts-nocheck
import ApiProxy from '../../services/api-proxy';
import {
  transformRecentCollectionsResponse,
  transformRecentItemsResponse,
  transformRecentToolsResponse,
  transformYourBookmarksResponse
} from '../../transformers';
import {
  FETCH_PROFILE_ERROR,
  FETCHED_PROFILE,
  IS_LOADING
} from '../actionTypes';

const toCamel = (s) => {
  return s.replace(/([-_][a-z])/gi, ($1) => {
    return $1.toUpperCase().replace('-', '').replace('_', '');
  });
};

const getTiles = async (tileSettings) => {
  const response = {};
  for (const tile in tileSettings) {
    if (tileSettings[tile]) {
      if (toCamel(tile) == 'showBookmarks') {
        const res = await ApiProxy.get('/your_bookmarks?page_size=5');
        const data = transformYourBookmarksResponse(res.data);
        response.bookmarks = data;
      } else if (toCamel(tile) == 'showRecentItems') {
        const res = await ApiProxy.get('/recent_items?page_size=5');
        const data = transformRecentItemsResponse(res.data);
        response.recentItems = data;
      } else if (toCamel(tile) == 'showRecentCollections') {
        const res = await ApiProxy.get('/collections/?page_size=3');
        const data = transformRecentCollectionsResponse(res.data);
        response.recentCollections = data;
      } else if (toCamel(tile) == 'showRecentTools') {
        const res = await ApiProxy.get('/recent_tools?page_size=2');
        const data = transformRecentToolsResponse(res.data);
        response.recentTools = data;
      }
    }
  }
  return response;
};

const getProfile = (dispatch) => {
  dispatch({
    type: IS_LOADING
  });
  ApiProxy.get('/your_profile')
    .then(async (profileResponse) => {
      const { user, ...selectedTiles } = profileResponse.data[0];
      const res = await getTiles(profileResponse.data[0]);
      const payload = {
        user,
        selectedTiles,
        ...res
      };
      dispatch({ type: FETCHED_PROFILE, payload });
    })
    .catch((err) => {
      dispatch({
        type: FETCH_PROFILE_ERROR,
        payload: err
      });
    });
};

export default getProfile;
