import React from "react";
import classNames from "classnames";

export function TrashIcon(props) {
  let width = 16;
  let height = 18;
  if (props.isNavIcon) {
    width = 60;
    height = 60;
  }

  const svgClasses = classNames("svg-inline--fa", "fa-trash-alt", "fa-w-14", {
    "navbutton-icon": props.isNavIcon,
    "button-icon": !props.isNavIcon,
  });

  return (
    <svg
      aria-hidden="true"
      focusable="false"
      data-prefix="fas"
      data-icon="trash-alt"
      className={svgClasses}
      role="img"
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 448 512"
      width={width}
      height={height}
    >
      <path
        fill="currentColor"
        d="M32 464a48 48 0 0 0 48 48h288a48 48 0 0 0 48-48V128H32zm272-256a16 16 0 0 1 32 0v224a16 16 0 0 1-32 0zm-96 0a16 16 0 0 1 32 0v224a16 16 0 0 1-32 0zm-96 0a16 16 0 0 1 32 0v224a16 16 0 0 1-32 0zM432 32H312l-9.4-18.7A24 24 0 0 0 281.1 0H166.8a23.72 23.72 0 0 0-21.4 13.3L136 32H16A16 16 0 0 0 0 48v32a16 16 0 0 0 16 16h416a16 16 0 0 0 16-16V48a16 16 0 0 0-16-16z"
      ></path>
    </svg>
  );
}