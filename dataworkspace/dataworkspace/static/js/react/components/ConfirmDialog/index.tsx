import React, { useEffect, useRef } from 'react';

import { SPACING_POINTS } from '@govuk-react/constants';
import { Button, H2, Link, Paragraph, WarningText } from 'govuk-react';
import styled from 'styled-components';

type ConfirmDialogProps = {
  actionUrl: string;
  bodyText: string;
  buttonTextAccept: string;
  buttonTextCancel: string;
  onClose: () => void;
  open: boolean;
  title: string;
  warning: boolean;
};

const ContainerButtonGroup = styled('div')`
  display: flex;
`;

const Dialog = styled('dialog')`
  padding: 30px 30px 0px;
  width: 600px;
`;

const StyledLink = styled(Link)`
  display: inline-block;
  font-size: 20px;
`;

const StyledForm = styled('form')`
  display: flex;
  align-items: baseline;
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
    <Dialog ref={refModal}>
      {props.warning ? (
        <H2 size="LARGE">{props.title}</H2>
      ) : (
        <WarningText>{props.title}</WarningText>
      )}
      {props.bodyText.length > 0 ? (
        <Paragraph>props.bodyText </Paragraph>
      ) : (
        <></>
      )}
      <ContainerButtonGroup>
        <StyledForm
          action={props.actionUrl}
          aria-label="form"
          method="GET"
          name="submit"
        >
          <Button
            style={{ marginRight: SPACING_POINTS[4] }}
            onSubmit={closeModal}
            type={'submit'}
          >
            {props.buttonTextAccept}
          </Button>
          <StyledLink href="javascript:;" onClick={props.onClose}>
            {props.buttonTextCancel}
          </StyledLink>
        </StyledForm>
      </ContainerButtonGroup>
    </Dialog>
  );
};

export default ConfirmDialog;
