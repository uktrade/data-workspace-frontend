import React, { useState } from 'react';

import Button from '@govuk-react/button';
import { SPACING_POINTS } from '@govuk-react/constants';
import { H2 } from '@govuk-react/heading';
import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { BLACK, ERROR_COLOUR, LIGHT_GREY } from '../../constants';
import { FeedbackResponse } from '../../services/inline-feedback';

const StyledForm = styled('form')`
  display: inline-flex;
  align-items: center;
  h2 {
    margin: 0 ${SPACING_POINTS[5]}px 0 0;
  }
  button {
    margin: 0;
  }
  button:first-of-type {
    margin-right: ${SPACING_POINTS[4]}px;
  }
`;

const StyledHeader = styled(H2)`
  margin-bottom: 0;
  + div {
    min-height: auto;
  }
`;

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  margin: 0;
  color: ${ERROR_COLOUR};
`;

export type AdditionalFormProps = {
  csrf_token: string;
  id: string;
  wasItHelpful: boolean;
  resetForm: () => void;
  setSuccessMessage: (message: string) => void;
};

export type InlineFeedbackProps = {
  title: string;
  location: string;
  customSuccessMessage?: string;
  postFeedback: (
    csrf_token: string,
    location: string,
    wasItHelpful: boolean
  ) => Promise<FeedbackResponse>;
  csrf_token: string;
  children?: ({
    csrf_token,
    id,
    wasItHelpful,
    resetForm
  }: AdditionalFormProps) => React.ReactNode;
};

const InlineFeedback: React.FC<InlineFeedbackProps> = ({
  title,
  location,
  customSuccessMessage,
  csrf_token,
  postFeedback,
  children
}) => {
  const [responseId, setResponseId] = useState<string>('');
  const [wasItHelpful, setWasItHelpful] = useState<boolean>(false);
  const [isSuccessfull, setIsSuccessfull] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();
  const [successMessage, setSuccessMessage] = useState<string | undefined>(
    'Thanks for letting us know, your response has been recorded.'
  );
  const resetForm = () => setIsSuccessfull(!isSuccessfull);

  const handleOnClick =
    (wasItHelpful: boolean) =>
    (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
      e.preventDefault();
      setLoading(true);
      postFeedback(csrf_token, location, wasItHelpful)
        .then((response) => {
          const { id } = response;
          setResponseId(id);
          setWasItHelpful(wasItHelpful);
          setIsSuccessfull(true);
          if (customSuccessMessage) {
            setSuccessMessage(customSuccessMessage);
          }
        })
        .catch((error) => {
          setError(error);
        })
        .finally(() => {
          setLoading(false);
        });
    };

  return (
    <LoadingBox loading={loading}>
      {error ? (
        <ErrorMessage data-testid="inline-feedback-error">
          Error: {error}
        </ErrorMessage>
      ) : isSuccessfull ? (
        <>
          <StyledHeader size="MEDIUM">{successMessage}</StyledHeader>
          {children?.({
            csrf_token,
            id: responseId,
            wasItHelpful,
            resetForm,
            setSuccessMessage
          })}
        </>
      ) : (
        <StyledForm>
          <H2 size="MEDIUM">{title}</H2>
          <Button
            buttonColour={LIGHT_GREY}
            buttonTextColour={BLACK}
            type="submit"
            onClick={handleOnClick(true)}
          >
            Yes
          </Button>
          <Button
            buttonColour={LIGHT_GREY}
            buttonTextColour={BLACK}
            type="submit"
            onClick={handleOnClick(false)}
          >
            No
          </Button>
        </StyledForm>
      )}
    </LoadingBox>
  );
};

export default InlineFeedback;
