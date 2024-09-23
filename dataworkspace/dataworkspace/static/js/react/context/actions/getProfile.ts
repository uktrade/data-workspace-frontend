// @ts-nocheck
import { fetchYourBookmarks } from '../../services';
import ApiProxy from '../../services/api-proxy';
import { recentItems } from '../../services/mocks';
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
  const response = {
    bookmarks: [],
    recentItems: [],
    recentTools: [],
    recentCollections: []
  };
  Object.keys(tileSettings).forEach(async (tile) => {
    if (tileSettings[tile]) {
      if (toCamel(tile) == 'showBookmarks') {
        const res = await ApiProxy.get('/your_bookmarks?page_size=5');
        const data = res.data.results;
        response.bookmarks.push(data);
      } else if (toCamel(tile) == 'showRecentItems') {
        const res = await ApiProxy.get('/recent_items?page_size=5');
        const data = res.data.results;
        response.recentItems.push(data);
      } else if (toCamel(tile) == 'showRecentCollections') {
        const res = await ApiProxy.get('/collections/?page_size=3');
        const data = res.data.results;
        response.recentCollections.push(data);
      } else if (toCamel(tile) == 'showRecentTools') {
        const res = await ApiProxy.get('/recent_tools?page_size=2');
        const data = res.data.results;
        response.recentTools.push(data);
      }
    }
  });
  return response;
};

const getProfile = (dispatch) => {
  dispatch({
    type: IS_LOADING
  });
  ApiProxy.get('/your_profile/')
    .then(async (res) => {
      res = await getTiles(res.data[0]);
      console.log(res);
      dispatch({ type: FETCHED_PROFILE, payload: res });
    })
    .catch((err) => {
      dispatch({
        type: FETCH_PROFILE_ERROR,
        payload: err
      });
    });
};

export default getProfile;
