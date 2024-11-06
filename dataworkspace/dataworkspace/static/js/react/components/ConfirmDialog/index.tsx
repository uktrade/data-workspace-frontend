/* eslint-disable */
import { useEffect, useRef } from 'react';
import Button from '@govuk-react/button';
import Heading from '@govuk-react/heading';
import Link from '@govuk-react/link';
import styled from 'styled-components';

interface ConfirmDialogProps {
  actionUrl: string;
  buttonText: string;
  onClose: () => void;
  open: boolean;
  title: string;
}

const ContainerButtonGroup = styled('div')`
  display: flex;
`;

const Dialog = styled('dialog')`
  padding-top: 25px;
`;

export const ConfirmDialog = (props: ConfirmDialogProps) => {
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
      <Heading size="LARGE">{props.title}</Heading>
      <ContainerButtonGroup>
        <form action={props.actionUrl} method="GET">
          <Button
            data-module="govuk-button"
            style={{ marginRight: '16px' }}
            onSubmit={closeModal}
            type={'submit'}
          >
            {props.buttonText}
          </Button>
          <Link
            href="javascript:;"
            onClick={props.onClose}
            style={{ fontSize: '1.4em', marginTop: '0.2em' }}
          >
            Cancel
          </Link>
        </form>
      </ContainerButtonGroup>
    </Dialog>
  );
};

export default ConfirmDialog;
