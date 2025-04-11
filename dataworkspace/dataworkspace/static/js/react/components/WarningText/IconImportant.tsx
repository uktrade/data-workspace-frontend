import React from 'react';

type Props = {
  fill?: string;
};

const IconImportant: React.FC<Props> = ({ fill = 'black', ...rest }: Props) => (
  <svg
    viewBox="0 0 100 100"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    {...rest}
  >
    {/* Outer circle */}
    <circle cx="50" cy="50" r="50" fill={fill} />

    {/* Exclamation mark stem */}
    <path d="M42 20 L55 20 L55 60 L44 60 Z" fill="white" />

    {/* Dot */}
    <circle cx="50" cy="76" r="9" fill="white" />
  </svg>
);

export default IconImportant;
