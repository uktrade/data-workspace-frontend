import { useEffect, useRef } from 'react';

import { FONT_SIZE, SPACING_POINTS } from '@govuk-react/constants';
import { Button, H2, Link } from 'govuk-react';
import styled from 'styled-components';

type ConfirmDialogProps = {
  actionUrl: string;
  buttonText: string;
  onClose: () => void;
  open: boolean;
  title: string;
};

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
      <H2 size="LARGE">{props.title}</H2>
      <ContainerButtonGroup>
        <form
          action={props.actionUrl}
          aria-label="form"
          method="GET"
          name="submitRemoveUser"
        >
          <Button
            style={{ marginRight: SPACING_POINTS[4] }}
            onSubmit={closeModal}
            type={'submit'}
          >
            {props.buttonText}
          </Button>
          <Link
            href="javascript:;"
            onClick={props.onClose}
            style={{
              display: 'inline-block',
              fontSize: FONT_SIZE.SIZE_24,
              marginTop: SPACING_POINTS[1]
            }}
          >
            Cancel
          </Link>
        </form>
      </ContainerButtonGroup>
    </Dialog>
  );
};

export default ConfirmDialog;
