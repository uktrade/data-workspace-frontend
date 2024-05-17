import React, { useState } from 'react';

import Button from '@govuk-react/button';
import { SPACING_POINTS } from '@govuk-react/constants';
import { H2 } from '@govuk-react/heading';
import { typography } from '@govuk-react/lib';
import LoadingBox from '@govuk-react/loading-box';
import styled from 'styled-components';

import { BLACK, ERROR_COLOUR, LIGHT_GREY } from '../../constants';

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

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  margin: 0;
  color: ${ERROR_COLOUR};
`;

export type PostFeedback = (
  location: string,
  wasItHelpful: boolean
) => Promise<void>;

export type InlineFeedbackProps = {
  title: string;
  location: string;
  successMessage: string;
  postFeedback: PostFeedback;
  children?: (location: string, wasItHelpful: boolean) => React.ReactNode;
};

const InlineFeedback: React.FC<InlineFeedbackProps> = ({
  title,
  location,
  successMessage,
  postFeedback,
  children
}) => {
  const [isSuccessfull, setIsSuccessfull] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [wasItHelpful, setWasItHelpful] = useState<boolean>(false);
  const [error, setError] = useState<string>();
  const handleOnClick =
    (wasItHelpful: boolean) =>
    (e: React.MouseEvent<HTMLButtonElement, MouseEvent>) => {
      e.preventDefault();
      setLoading(true);
      // we are using then to only catch promise rejection and not other JS errors
      postFeedback(location, wasItHelpful)
        .catch((error) => {
          if (typeof error === 'string') {
            setError(error);
          } else {
            throw new Error(
              'The postFeedback function must only ever reject with a string'
            );
          }
          setLoading(false);
        })
        .then(() => {
          setIsSuccessfull(true);
          setWasItHelpful(wasItHelpful);
          setLoading(false);
        });
    };
  return (
    <LoadingBox loading={loading}>
      {error ? (
        <ErrorMessage data-testid="data-usage-error">
          Error: {error}
        </ErrorMessage>
      ) : isSuccessfull ? (
        <>
          <H2 size="MEDIUM">{successMessage}</H2>
          {children?.(location, wasItHelpful)}
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
