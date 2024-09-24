// @ts-nocheck
import React, { useEffect, useRef } from 'react';

import styled from 'styled-components';

const Dialog = styled('dialog')`
  padding: 0px;
`;

export const Modal = ({ isModalOpen, closeModal, children }) => {
  const refModal = useRef();

  useEffect(() => {
    if (isModalOpen) {
      refModal.current?.showModal();
    } else {
      refModal.current?.close();
    }
  }, [isModalOpen]);

  return (
    <Dialog ref={refModal} onCancel={closeModal}>
      {children}
    </Dialog>
  );
};

export default Modal;
