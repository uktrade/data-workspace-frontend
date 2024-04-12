// @ts-nocheck
import { useCallback, useReducer } from 'react';

export const useReducerWithThunk = (reducer, initialState) => {
  const [state, dispatch] = useReducer(reducer, initialState);

  function customDispatch(action) {
    if (typeof action === 'function') {
      return action(customDispatch);
    } else {
      dispatch(action);
    }
  }

  // Memoize so you can include it in the dependency array without causing infinite loops
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const stableDispatch = useCallback(customDispatch, [dispatch]);

  return [state, stableDispatch];
};
