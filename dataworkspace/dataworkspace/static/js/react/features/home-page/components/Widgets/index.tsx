// @ts-nocheck
import { useContext, useEffect } from 'react';
import { useForm } from 'react-hook-form';

import Button from '@govuk-react/button';
import { FONT_SIZE, SPACING_POINTS } from '@govuk-react/constants';
import { MEDIA_QUERIES, SPACING_POINTS } from '@govuk-react/constants';
import { typography } from '@govuk-react/lib';
import {
  Checkbox,
  H2,
  Link,
  ListItem,
  LoadingBox,
  UnorderedList
} from 'govuk-react';
import styled from 'styled-components';

import Modal from '../../../../components/Modal';
import { MID_GREY, WHITE } from '../../../../constants';
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

const WidgetsInner = styled('div')`
    ${MEDIA_QUERIES.TABLET} {
      display: grid;
      grid-template-columns: 1fr 1fr;
      grid-gap: 30px;
      > div {
        margin-bottom: ${SPACING_POINTS['6']}px;
        &:last-child {
          margin-bottom: 0;
        }
      }
    }
  }
`;

const StyledParagraph = styled('p')`
  ${typography.font({ size: 16 })};
`;

const StyledLoadingBox = styled(LoadingBox)`
  min-height: 500px;
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

const StyledSpan = styled('span')`
  display: inline-block;
  font-size: ${FONT_SIZE.SIZE_19};
  margin-bottom: 20px;
`;

const InfoBox = styled('div')`
  padding: ${SPACING_POINTS['4']}px;
  border: 1px solid ${MID_GREY};
  background-color: ${WHITE};
`;

const Widgets = ({ token }) => {
  const { homePageDispatch, homePageState } = useContext(HomePageContext);
  const { data, loading, user, error, hasSelectedTiles, modalOpen } =
    homePageState;

  const { register, handleSubmit } = useForm({
    defaultValues: data.selectedTiles,
    values: data.selectedTiles
  });

  const dispatch = homePageDispatch;
  useEffect(() => {
    getProfile(homePageDispatch);
  }, []);

  const handleOnSubmit = async (data) => {
    await ApiProxy.patch(`/your_profile/${user}`, data, token);
    dispatch({ type: CLOSE_HOMEPAGE_MODAL });
    getProfile(homePageDispatch);
  };
  return (
    <>
      <StyledSpan>
        <StyledLink
          href="#"
          onClick={() => dispatch({ type: OPEN_HOMEPAGE_MODAL })}
        >
          {hasSelectedTiles
            ? 'Edit homepage preferences'
            : 'Add some new widgets to your homepage'}
        </StyledLink>
      </StyledSpan>
      <StyledLoadingBox loading={loading}>
        {hasSelectedTiles ? (
          <WidgetsInner id="widgets">
            {data.recentCollections && (
              <RecentCollections collections={data.recentCollections} />
            )}
            {data.recentItems && <RecentItems items={data.recentItems} />}
            {data.recentTools && <RecentTools tools={data.recentTools} />}
            {data.bookmarks && <YourBookmarks bookmarks={data.bookmarks} />}
          </WidgetsInner>
        ) : (
          <InfoBox>
            <H2 size="MEDIUM">You currently have no widgets to display!</H2>
            <StyledParagraph>
              Did you know you can add lots of useful information to the
              homepage:
            </StyledParagraph>
            <UnorderedList>
              <ListItem>Add your bookmarks</ListItem>
              <ListItem>List recent datasets you have visited</ListItem>
              <ListItem>List your recent collections</ListItem>
              <ListItem>List your recent tool activity</ListItem>
            </UnorderedList>
          </InfoBox>
        )}
      </StyledLoadingBox>
      <Modal isModalOpen={modalOpen}>
        <ModalInner>
          <H2 size="MEDIUM">Choose what widgets you would like to display:</H2>
          <form onSubmit={handleSubmit(handleOnSubmit)}>
            <Checkbox {...register('show_bookmarks')}>Bookmarks</Checkbox>
            <Checkbox {...register('show_recent_items')}>
              Recently visited items
            </Checkbox>
            <Checkbox {...register('show_recent_tools')}>Recent tools</Checkbox>
            <Checkbox {...register('show_recent_collections')}>
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
