// @ts-nocheck
import { useContext, useEffect } from 'react';

import getProfile from '../../../../context/actions/getProfile';
import { HomePageContext } from '../../../../context/provider';

const TilesContainer = () => {
  const { homePageDispatch, homePageState } = useContext(HomePageContext);
  const { data, loading, error } = homePageState;
  console.log('homePageState', homePageState);
  useEffect(() => {
    getProfile(homePageDispatch);
  }, []);

  return <>Hello world</>;
};

export default TilesContainer;
