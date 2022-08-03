import React from "react";

export class Header extends React.Component {
  constructor(props) {
    super(props);
  }

  handleRefreshClick() {
    // Todo - spin the icon
    this.props.onRefreshClick();
  }

  render() {
    const breadCrumbs = this.props.breadCrumbs.map((b) => {
      return (
        <li
          onClick={() => this.props.onBreadcrumbClick(b)}
          className="browser-breadcrumb"
          key={b.prefix}
        >
          <a className="browser-breadcrumb-link">{b.label}</a>
        </li>
      );
    });
    return (
      <div className="browser-header">
        <button className="navbutton" onClick={() => this.handleRefreshClick()}>
          <svg
            spinner="refresh"
            aria-hidden="true"
            focusable="false"
            data-prefix="fas"
            data-icon="sync"
            className="navbutton-icon navbutton-icon-small svg-inline--fa fa-sync fa-w-16"
            role="img"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 512 512"
            width="60"
            height="60"
          >
            <path
              fill="currentColor"
              d="M440.65 12.57l4 82.77A247.16 247.16 0 0 0 255.83 8C134.73 8 33.91 94.92 12.29 209.82A12 12 0 0 0 24.09 224h49.05a12 12 0 0 0 11.67-9.26 175.91 175.91 0 0 1 317-56.94l-101.46-4.86a12 12 0 0 0-12.57 12v47.41a12 12 0 0 0 12 12H500a12 12 0 0 0 12-12V12a12 12 0 0 0-12-12h-47.37a12 12 0 0 0-11.98 12.57zM255.83 432a175.61 175.61 0 0 1-146-77.8l101.8 4.87a12 12 0 0 0 12.57-12v-47.4a12 12 0 0 0-12-12H12a12 12 0 0 0-12 12V500a12 12 0 0 0 12 12h47.35a12 12 0 0 0 12-12.6l-4.15-82.57A247.17 247.17 0 0 0 255.83 504c121.11 0 221.93-86.92 243.55-201.82a12 12 0 0 0-11.8-14.18h-49.05a12 12 0 0 0-11.67 9.26A175.86 175.86 0 0 1 255.83 432z"
            ></path>
          </svg>
        </button>
        <ul className="govuk-body browser-breadcrumbs">{breadCrumbs}</ul>
        <button
          className="navbutton"
          title="Create folder"
          onClick={() => this.props.onNewFolderClick(this.props.currentPrefix)}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            data-prefix="fas"
            data-icon="folder-plus"
            className="navbutton-icon navbutton-icon-large svg-inline--fa fa-folder-plus fa-w-16"
            role="img"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 512 512"
            width="60"
            height="60"
          >
            <path
              fill="currentColor"
              d="M464 128H272l-64-64H48C21.49 64 0 85.49 0 112v288c0 26.51 21.49 48 48 48h416c26.51 0 48-21.49 48-48V176c0-26.51-21.49-48-48-48zm-96 168c0 8.84-7.16 16-16 16h-72v72c0 8.84-7.16 16-16 16h-16c-8.84 0-16-7.16-16-16v-72h-72c-8.84 0-16-7.16-16-16v-16c0-8.84 7.16-16 16-16h72v-72c0-8.84 7.16-16 16-16h16c8.84 0 16 7.16 16 16v72h72c8.84 0 16 7.16 16 16v16z"
            ></path>
          </svg>
        </button>
        <button
          className="navbutton"
          title="Upload files"
          onClick={() => this.props.onUploadClick(this.props.currentPrefix)}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            data-prefix="fas"
            data-icon="cloud-upload-alt"
            className="navbutton-icon svg-inline--fa fa-cloud-upload-alt fa-w-20"
            role="img"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 640 512"
            width="60"
            height="60"
          >
            <path
              fill="currentColor"
              d="M537.6 226.6c4.1-10.7 6.4-22.4 6.4-34.6 0-53-43-96-96-96-19.7 0-38.1 6-53.3 16.2C367 64.2 315.3 32 256 32c-88.4 0-160 71.6-160 160 0 2.7.1 5.4.2 8.1C40.2 219.8 0 273.2 0 336c0 79.5 64.5 144 144 144h368c70.7 0 128-57.3 128-128 0-61.9-44-113.6-102.4-125.4zM393.4 288H328v112c0 8.8-7.2 16-16 16h-48c-8.8 0-16-7.2-16-16V288h-65.4c-14.3 0-21.4-17.2-11.3-27.3l105.4-105.4c6.2-6.2 16.4-6.2 22.6 0l105.4 105.4c10.1 10.1 2.9 27.3-11.3 27.3z"
            ></path>
          </svg>
        </button>

        <button
          className="navbutton"
          title="Delete selected items"
          onClick={() => this.props.onDeleteClick()}
        >
          <svg
            aria-hidden="true"
            focusable="false"
            data-prefix="fas"
            data-icon="trash-alt"
            className="navbutton-icon svg-inline--fa fa-trash-alt fa-w-14"
            role="img"
            xmlns="http://www.w3.org/2000/svg"
            viewBox="0 0 448 512"
            width="60"
            height="60"
          >
            <path
              fill="currentColor"
              d="M32 464a48 48 0 0 0 48 48h288a48 48 0 0 0 48-48V128H32zm272-256a16 16 0 0 1 32 0v224a16 16 0 0 1-32 0zm-96 0a16 16 0 0 1 32 0v224a16 16 0 0 1-32 0zm-96 0a16 16 0 0 1 32 0v224a16 16 0 0 1-32 0zM432 32H312l-9.4-18.7A24 24 0 0 0 281.1 0H166.8a23.72 23.72 0 0 0-21.4 13.3L136 32H16A16 16 0 0 0 0 48v32a16 16 0 0 0 16 16h416a16 16 0 0 0 16-16V48a16 16 0 0 0-16-16z"
            ></path>
          </svg>
        </button>
      </div>
    );
  }
}
