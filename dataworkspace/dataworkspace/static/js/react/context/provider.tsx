// @ts-nocheck
import React, { createContext, useReducer } from 'react';

import { homePageInitialState, homePageReducer } from './reducers';

export const HomePageContext = createContext({});

export const HomePageProvider = ({
  children
}: {
  children: React.ReactNode;
}) => {
  const [homePageState, homePageDispatch] = useReducer(
    homePageReducer,
    homePageInitialState
  );

  return (
    <HomePageContext.Provider
      value={{
        homePageState,
        homePageDispatch
      }}
    >
      {children}
    </HomePageContext.Provider>
  );
};
