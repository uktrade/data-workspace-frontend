// @ts-nocheck
import { fetchHomepageTiles } from '../../services';

export const initialState = {
  isLoading: false,
  tiles: {
    bookmarks: false,
    recent_collections: false,
    recent_tools: false,
    recent_items: false
  }
};

export const homePageReducer = async (state, action) => {
  switch (action.type) {
    case 'IS_LOADING':
      return { ...state, isLoading: true };
    case 'FETCH_TILES':
      const result = await fetchHomepageTiles();
      console.log(result);
      return {
        ...state,
        // tiles: action.payload.user_profile.homepage_tiles,
        isLoading: false
      };
    default:
      return state;
  }
};
