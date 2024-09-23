// @ts-nocheck
import { FETCHED_PROFILE, IS_LOADING } from '../actionTypes';

export const homePageInitialState = {
  isLoading: false,
  error: null,
  data: []
};

export const homePageReducer = (state, { type, payload }) => {
  switch (type) {
    case IS_LOADING:
      return { ...state, isLoading: true };
    case FETCHED_PROFILE:
      return {
        ...state,
        isLoading: false,
        data: payload
      };
    default:
      return state;
  }
};
