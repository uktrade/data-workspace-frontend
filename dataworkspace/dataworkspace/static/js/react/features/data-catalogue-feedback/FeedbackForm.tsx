import { useState } from 'react';
import { SubmitHandler, useForm, UseFormRegisterReturn } from 'react-hook-form';

import Button from '@govuk-react/button';
import Checkbox from '@govuk-react/checkbox';
import {
  FONT_SIZE,
  FONT_WEIGHTS,
  SPACING_POINTS
} from '@govuk-react/constants';
import { Fieldset } from '@govuk-react/fieldset';
import { typography } from '@govuk-react/lib';
import Link from '@govuk-react/link';
import LoadingBox from '@govuk-react/loading-box';
import { TextArea } from '@govuk-react/text-area';
import styled from 'styled-components';

import { ERROR_COLOUR } from '../../constants';
import type { FeedbackResponse } from '../../services/inline-feedback';

const FormActions = styled('div')`
  display: inline-flex;
  gap: 27px;
  align-items: center;
  margin-top: ${SPACING_POINTS[8]}px;
  button {
    margin: 0;
  }
`;

const StyledLink = styled(Link)`
  font-size: ${FONT_SIZE.SIZE_19};
`;

const StyledFieldset = styled(Fieldset)`
  margin-top: ${SPACING_POINTS[6]}px;
  margin-bottom: ${SPACING_POINTS[4]}px;
  legend {
    margin-bottom: ${SPACING_POINTS[3]}px;
  }
`;

const StyledTextArea = styled(TextArea)`
  span {
    font-weight: ${FONT_WEIGHTS.bold};
    margin-bottom: ${SPACING_POINTS[3]}px;
    padding-bottom: 0;
  }
  textarea {
    font-weight: ${FONT_WEIGHTS.regular};
  }
`;

const ErrorMessage = styled('p')`
  ${typography.font({ size: 19 })};
  margin: 0;
  color: ${ERROR_COLOUR};
`;

type FormValues = {
  choices: string[];
  more_detail: string;
};

const Options = ({
  choice,
  register
}: {
  choice: 'yes' | 'no';
  register: UseFormRegisterReturn<'choices'>;
}) => {
  const options = {
    yes: [
      'I found the information I needed',
      'It was easy to find relevant datasets',
      'The filters helped me narrow down my search results',
      'It was easy to determine what datasets could be useful',
      'Other'
    ],
    no: [
      'I did not find the information I needed',
      'It was hard to find relevant datasets',
      'The filters did not help me find relevant datasets',
      'It was hard to determine what datasets could be useful',
      'Other'
    ]
  };
  return options[choice].map((option) => (
    <Checkbox key={option} value={option} {...register}>
      {option}
    </Checkbox>
  ));
};

const FeedbackForm = ({
  id,
  csrf_token,
  wasItHelpful,
  resetForm,
  patchFeedback,
  setSuccessMessage
}: {
  id: string;
  csrf_token: string;
  wasItHelpful: boolean;
  resetForm: () => void;
  setSuccessMessage: (message: string) => void;
  patchFeedback: (
    csrf_token: string,
    id: string,
    payload: { inline_feedback_choices: string; more_detail: string }
  ) => Promise<FeedbackResponse>;
}) => {
  const { register, handleSubmit } = useForm<FormValues>();
  const [isSuccessfull, setIsSuccessfull] = useState<boolean>(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string>();

  const handleOnSubmit: SubmitHandler<FormValues> = (data) => {
    const payload = {
      more_detail: data.more_detail,
      inline_feedback_choices: data.choices ? data.choices.join(',') : ''
    };
    setLoading(true);
    patchFeedback(csrf_token, id, payload)
      .then(() => {
        setIsSuccessfull(true);
        setSuccessMessage('Thanks for your feedback.');
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
        <ErrorMessage data-testid="feedback-error">Error: {error}</ErrorMessage>
      ) : isSuccessfull ? null : (
        <form
          onSubmit={handleSubmit(handleOnSubmit)}
          data-test="additional-feedback"
        >
          {wasItHelpful ? (
            <>
              <StyledFieldset>
                <Fieldset.Legend size="SMALL">
                  Tell us more about why this page was helpful (optional)
                </Fieldset.Legend>
                <Options register={register('choices')} choice="yes" />
              </StyledFieldset>
              <StyledTextArea input={register('more_detail')}>
                Is there anything else you can tell us? (optional)
              </StyledTextArea>
            </>
          ) : (
            <>
              <StyledFieldset>
                <Fieldset.Legend size="SMALL">
                  Tell us more about your experience (optional)
                </Fieldset.Legend>
                <Options register={register('choices')} choice="no" />
              </StyledFieldset>
              <StyledTextArea input={register('more_detail')}>
                Help us improve this page by giving more detail (optional)
              </StyledTextArea>
            </>
          )}
          <FormActions>
            <Button type="submit">Send feedback</Button>{' '}
            <StyledLink
              href="#"
              onClick={(e) => {
                e.preventDefault();
                resetForm();
              }}
            >
              Cancel
            </StyledLink>
          </FormActions>
        </form>
      )}
    </LoadingBox>
  );
};

export default FeedbackForm;
