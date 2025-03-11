import React, { useState } from 'react';

import { Button } from '@govuk-react/button';
import Table from '@govuk-react/table';
import { Paragraph } from 'govuk-react';
import styled from 'styled-components';

import ConfirmDialog from '../../components/ConfirmDialog/';

const RemoveUserTableCell = styled(Table.Cell)`
  vertical-align: middle;
  text-align: right;
`;

const SpanBold = styled('span')`
  font-weight: bold;
`;

const UserNameTableCell = styled(Table.Cell)`
  padding-bottom: 1px;
`;

type User = {
  data_catalogue_editor: boolean;
  email: string;
  first_name: string;
  iam: boolean;
  iao: boolean;
  id: string;
  last_name: string;
  remove_user_url: string;
};

const UserTypeSuffix: React.FC<Record<'user', User>> = function ({ user }) {
  if (user.iam) {
    return '(Information Asset Manager)';
  } else if (user.iao) {
    return '(Information Asset Owner)';
  }
  return null;
};

const ConfirmRemoveUser = ({
  data
}: {
  data: Array<User>;
}): React.ReactNode => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<User | null>(null);

  const closeModal = () => {
    setIsOpen(false);
    setSelectedUser(null);
  };
  const openModal = (user: User) => {
    setSelectedUser(user);
    setIsOpen(true);
  };
  return (
    <>
      {data.length && (
        <div>
          <Table>
            {data.map((user) => (
              <Table.Row key={user.id}>
                <UserNameTableCell>
                  <SpanBold>{`${user.first_name} ${user.last_name} `}</SpanBold>
                  <UserTypeSuffix user={user} />
                  <Paragraph>{user.email}</Paragraph>
                </UserNameTableCell>
                {[user.iam, user.iao].some((x) => x == true) ? (
                  <Table.Cell></Table.Cell>
                ) : (
                  <RemoveUserTableCell>
                    <Button
                      buttonColour="#f3f2f1"
                      buttonTextColour="#0b0c0c"
                      onClick={() => openModal(user)}
                      style={{ marginBottom: 0 }}
                    >
                      Remove user
                    </Button>
                  </RemoveUserTableCell>
                )}
              </Table.Row>
            ))}
          </Table>
        </div>
      )}
      {isOpen && selectedUser && (
        <ConfirmDialog
          actionUrl={selectedUser.remove_user_url}
          title={`Are you sure you want to remove ${selectedUser?.first_name} ${selectedUser?.last_name}'s access to this data?`}
          open={isOpen}
          onClose={closeModal}
          buttonTextAccept={'Yes, remove user'}
          buttonTextCancel={'Cancel'}
          warning={false}
        ></ConfirmDialog>
      )}
    </>
  );
};

export default ConfirmRemoveUser;
