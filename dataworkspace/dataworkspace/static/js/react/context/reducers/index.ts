// @ts-nocheck
import {
  CLOSE_HOMEPAGE_MODAL,
  FETCHED_PROFILE,
  IS_LOADING,
  OPEN_HOMEPAGE_MODAL
} from '../actionTypes';

export const homePageInitialState = {
  user: null,
  loading: true,
  modalOpen: false,
  error: null,
  selectedTiles: null,
  data: []
};

export const homePageReducer = (state, { type, payload }) => {
  switch (type) {
    case IS_LOADING:
      return { ...state, loading: true };
    case FETCHED_PROFILE:
      return {
        ...state,
        user: payload.user,
        selectedTiles: payload.selectedTiles,
        data: payload,
        loading: false
      };
    case OPEN_HOMEPAGE_MODAL:
      return {
        ...state,
        modalOpen: true
      };
    case CLOSE_HOMEPAGE_MODAL:
      return {
        ...state,
        modalOpen: false
      };
    default:
      return state;
  }
};
