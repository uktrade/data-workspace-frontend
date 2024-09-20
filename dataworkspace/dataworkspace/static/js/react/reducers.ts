// @ts-nocheck
import { FETCH_PROFILE, IS_LOADING } from './actions';
import ApiProxy from './services/api-proxy';

export const homePageInitialState = {
  isLoading: false,
  error: null,
  tiles: []
};

export const homePageReducer = async (state, action) => {
  switch (action.type) {
    case IS_LOADING:
      return { ...state, isLoading: true };
    case FETCH_PROFILE:
      const { data, status, message } = await ApiProxy.get('/your_profile');
      return {
        ...state,
        tiles: data,
        isLoading: false,
        error: data.message
      };
    default:
      return state;
  }
};
