// @ts-nocheck
import { useContext, useEffect } from 'react';
import { useForm } from 'react-hook-form';

import Button from '@govuk-react/button';
import { FONT_SIZE, SPACING_POINTS } from '@govuk-react/constants';
import { Checkbox, H2, Link, LoadingBox } from 'govuk-react';
import styled from 'styled-components';

import Modal from '../../../../components/Modal';
import getProfile from '../../../../context/actions/getProfile';
import {
  CLOSE_HOMEPAGE_MODAL,
  OPEN_HOMEPAGE_MODAL
} from '../../../../context/actionTypes';
import { HomePageContext } from '../../../../context/provider';
import ApiProxy from '../../../../services/api-proxy';
import RecentCollections from '../RecentCollections';
import RecentItems from '../RecentItems';
import RecentTools from '../RecentTools';
import YourBookmarks from '../YourBookmarks';

const StyledLoadingBox = styled(LoadingBox)`
  min-height: 500px;
`;

const StyledDiv = styled('div')`
  margin-bottom: 20px;
`;

const ModalInner = styled('div')`
  border: 2px solid black;
  padding: 30px !important;
`;

const FormActions = styled('div')`
  display: inline-flex;
  gap: 27px;
  align-items: center;
  margin-top: ${SPACING_POINTS[4]}px;
  button {
    margin: 0;
  }
`;

const StyledLink = styled(Link)`
  font-size: ${FONT_SIZE.SIZE_19};
`;

const Widgets = ({ token }) => {
  const { homePageDispatch, homePageState } = useContext(HomePageContext);
  const { data, loading, user, selectedTiles, error, modalOpen } =
    homePageState;

  console.log(selectedTiles);
  const { register, handleSubmit } = useForm({
    defaultValues: {
      ...selectedTiles
    }
  });
  const dispatch = homePageDispatch;
  useEffect(() => {
    getProfile(homePageDispatch);
  }, []);

  const handleOnSubmit = (data) => {
    console.log('data', homePageState);
    ApiProxy.patch(`/your_profile/${user}`, data, token);
  };
  return (
    <>
      <StyledDiv>
        <Link href="#" onClick={() => dispatch({ type: OPEN_HOMEPAGE_MODAL })}>
          Edit homepage
        </Link>
      </StyledDiv>
      <StyledLoadingBox loading={loading}>
        <>
          {data.recentCollections && (
            <RecentCollections collections={data.recentCollections} />
          )}
          {data.recentItems && <RecentItems items={data.recentItems} />}
          {data.recentTools && <RecentTools tools={data.recentTools} />}
          {data.bookmarks && <YourBookmarks bookmarks={data.bookmarks} />}
        </>
      </StyledLoadingBox>
      <Modal isModalOpen={modalOpen}>
        <ModalInner>
          <H2 size="MEDIUM">Choose what widgets you would like to display:</H2>
          <form onSubmit={handleSubmit(handleOnSubmit)}>
            <Checkbox value={true} {...register('show_bookmarks')}>
              Bookmarks
            </Checkbox>
            <Checkbox value={true} {...register('show_recent_items')}>
              Recently visited items
            </Checkbox>
            <Checkbox value={true} {...register('show_recent_tools')}>
              Recent tools
            </Checkbox>
            <Checkbox value={true} {...register('show_recent_collections')}>
              Recent collections
            </Checkbox>
            <FormActions>
              <Button type="submit">Save</Button>{' '}
              <StyledLink
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  dispatch({ type: CLOSE_HOMEPAGE_MODAL });
                }}
              >
                Cancel
              </StyledLink>
            </FormActions>
          </form>
        </ModalInner>
      </Modal>
    </>
  );
};

export default Widgets;
