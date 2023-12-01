import { MEDIA_QUERIES, SITE_WIDTH, SPACING } from '@govuk-react/constants';
import styled from 'styled-components';

const InnerContainer = styled('div')({
  maxWidth: SITE_WIDTH,
  marginLeft: SPACING.SCALE_3,
  marginRight: SPACING.SCALE_3,
  textAlign: 'left',
  [MEDIA_QUERIES.LARGESCREEN]: {
    marginLeft: SPACING.SCALE_5,
    marginRight: SPACING.SCALE_5
  },
  // no 1020px breakpoint in constants yet
  '@media only screen and (min-width:1020px)': {
    margin: '0 auto'
  }
});

export default InnerContainer;
