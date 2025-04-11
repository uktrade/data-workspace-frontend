import React, { useEffect, useRef } from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { Button, H2, Link, Paragraph } from 'govuk-react';
import styled from 'styled-components';

import WarningText from '../WarningText';

type ConfirmDialogProps = {
  actionUrl: string;
  bodyText?: string;
  children?: React.ReactNode;
  buttonTextAccept: string;
  buttonColourAccept?: string;
  buttonTextCancel: string;
  buttonValueAccept?: string;
  csrf_token?: string;
  onClose: () => void;
  open: boolean;
  title: string;
  warning?: boolean;
};

const ContainerButtonGroup = styled('div')`
  display: flex;
`;

const Dialog = styled('dialog')<Pick<ConfirmDialogProps, 'warning'>>`
  padding: 30px 30px 0px;
  width: ${(props) => (props.warning === true ? '659px' : '600px')};
`;

const StyledParagraph = styled(Paragraph)`
  padding-top: 30px;
`;

const StyledLink = styled(Link)`
  display: inline-block;
  font-size: 20px;
`;

const StyledForm = styled('form')`
  display: flex;
  align-items: baseline;
`;

const StyledWarning = styled(WarningText)`
  > strong {
    font-size: 27px;
  }
`;

export const ConfirmDialog: React.FC<ConfirmDialogProps> = (props) => {
  const refModal = useRef<HTMLDialogElement>(null);
  const closeModal = function () {
    refModal.current?.close();
  };
  useEffect(() => {
    if (props.open) {
      refModal.current?.showModal();
    } else {
      refModal.current?.close();
    }
  }, [props.open]);
  return (
    <Dialog
      data-test="confirmation-dialog"
      ref={refModal}
      warning={props.warning}
    >
      {props.warning ? (
        <StyledWarning>{props.title}</StyledWarning>
      ) : (
        <H2 size="LARGE">{props.title}</H2>
      )}
      {props.bodyText && props.bodyText.length > 0 && (
        <StyledParagraph>{props.bodyText}</StyledParagraph>
      )}

      {props.children}

      <ContainerButtonGroup>
        <StyledForm
          action={props.actionUrl}
          aria-label="form"
          method={props.warning === true ? 'POST' : 'GET'}
          name="submit"
        >
          {props.warning === true ? (
            <input
              type="hidden"
              name="csrfmiddlewaretoken"
              value={props.csrf_token}
            ></input>
          ) : (
            <></>
          )}
          <Button
            name={'action'}
            style={{ marginRight: SPACING_POINTS[4] }}
            onSubmit={closeModal}
            type={'submit'}
            value={props.buttonValueAccept ?? ''}
            buttonColour={props.buttonColourAccept}
          >
            {props.buttonTextAccept}
          </Button>
          {props.warning === false ? (
            <StyledLink href="javascript:;" onClick={props.onClose}>
              {props.buttonTextCancel}
            </StyledLink>
          ) : (
            <Button
              buttonColour="#f3f2f1"
              buttonShadowColour="#929191"
              buttonTextColour="#0b0c0c"
              onClick={props.onClose}
              style={{ marginLeft: '-10px' }}
            >
              Close
            </Button>
          )}
        </StyledForm>
      </ContainerButtonGroup>
    </Dialog>
  );
};

export default ConfirmDialog;
