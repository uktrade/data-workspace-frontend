import React from 'react';

import InlineFeedback from '../../components/InlineFeedback/';
import { patchFeedback, postFeedback } from '../../services';
import FeedbackForm from './FeedbackForm';

const DataCatalogueFeedback: React.FC<Record<'csrf_token', string>> = ({
  csrf_token
}) => (
  <InlineFeedback
    title="Was this page helpful?"
    location="data-catalogue"
    postFeedback={postFeedback}
    csrf_token={csrf_token}
  >
    {(props) => <FeedbackForm patchFeedback={patchFeedback} {...props} />}
  </InlineFeedback>
);

export default DataCatalogueFeedback;
