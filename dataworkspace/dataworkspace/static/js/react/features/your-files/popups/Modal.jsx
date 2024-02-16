import React, { useEffect, useRef } from 'react';
import styled from 'styled-components';

const Dialog = styled('dialog')`
  padding: 0px;
  width: 640px;
`;

export const Modal = ({ isModalOpen, closeModal, children }) => {
  const ref = useRef();

  useEffect(() => {
    if (isModalOpen) {
      ref.current?.showModal();
    } else {
      ref.current?.close();
    }
  }, [isModalOpen]);

  return (
    <Dialog ref={ref} onCancel={closeModal}>
      {children}
    </Dialog>
  );
};

export default Modal;
