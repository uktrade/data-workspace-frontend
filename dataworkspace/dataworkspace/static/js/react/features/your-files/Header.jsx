/* eslint-disable */
import React from 'react';
import { TrashIcon } from './icons/trash';
import { UploadIcon } from './icons/upload';
import { NewFolderIcon } from './icons/newfolder';

export class Header extends React.Component {
  constructor(props) {
    super(props);
    this.state = { spin: false };
  }

  handleRefreshClick() {
    this.props.onRefreshClick();
    this.setState({ spin: true });
  }

  render() {
    const breadCrumbs = this.props.breadCrumbs.reverse().map((b) => {
      return (
        <li className="browser-breadcrumb" key={b.prefix}>
          &nbsp;
          <a
            href=""
            onClick={(e) => this.props.onBreadcrumbClick(e, b)}
            className="browser-breadcrumb-link"
          >
            {b.label}
          </a>
          &nbsp;
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
            className={`navbutton-icon navbutton-icon-small svg-inline--fa fa-sync fa-w-16${this.state.spin ? ' spin' : ''}`}
            onAnimationEnd={() => this.setState({ spin: false })}
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
          <NewFolderIcon isNavIcon={true} />
        </button>
        <button
          className="navbutton"
          title="Upload files"
          onClick={() => this.props.onUploadClick(this.props.currentPrefix)}
        >
          <UploadIcon isNavIcon={true} />
        </button>

        <button
          className="navbutton"
          title="Delete selected items"
          onClick={() => this.props.onDeleteClick()}
          disabled={!this.props.canDelete}
        >
          <TrashIcon isNavIcon={true} />
        </button>
      </div>
    );
  }
}
