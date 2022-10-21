import React from "react";
import "./FileList.css";

import { prefixToFolder, bytesToSize, fullPathToFilename } from "./utils";

function TableHeader(props) {
  return (
    <tr className="govuk-table__row">
      <td className="govuk-table__header govuk-table__header--checkbox"></td>

      <th scope="col" className="govuk-table__header">
        Name
      </th>
      <th scope="col" className="govuk-table__header" style={{ width: "15em" }}>
        Last modified
      </th>
      <th
        scope="col"
        className="govuk-table__header govuk-table__header--numeric"
        style={{ width: "5em" }}
      >
        Size
      </th>
      <th scope="col" className="govuk-table__header" style={{ width: "8em" }}>
        &nbsp;
      </th>
    </tr>
  );
}

function TableRowBigDataFolder(props) {
  const folderName = prefixToFolder(props.folder.Prefix);
  return (
    <tr className="govuk-table__row">
      <td
        className="govuk-table__cell govuk-table__cell--checkbox"
        title="This folder cannot be deleted"
      >
        <svg
          aria-hidden="true"
          focusable="false"
          data-prefix="fas"
          data-icon="database"
          className="svg-inline--fa fa-database fa-w-14"
          role="img"
          xmlns="http://www.w3.org/2000/svg"
          viewBox="0 0 448 512"
          style={{ marginTop: "10px", height: "24px", marginLeft: "2px" }}
          width="21"
          height="24"
        >
          <path
            fill="currentColor"
            d="M448 73.143v45.714C448 159.143 347.667 192 224 192S0 159.143 0 118.857V73.143C0 32.857 100.333 0 224 0s224 32.857 224 73.143zM448 176v102.857C448 319.143 347.667 352 224 352S0 319.143 0 278.857V176c48.125 33.143 136.208 48.572 224 48.572S399.874 209.143 448 176zm0 160v102.857C448 479.143 347.667 512 224 512S0 479.143 0 438.857V336c48.125 33.143 136.208 48.572 224 48.572S399.874 369.143 448 336z"
          ></path>
        </svg>
      </td>
      <td className="govuk-table__cell">
        <a
          draggable="false"
          className="folder govuk-link govuk-link--no-visited"
          onClick={(e) => {
            e.preventDefault();
            props.onClick();
            return false;
          }}
          href="#"
        >
          {folderName}
        </a>
      </td>
      <td className="govuk-table__cell"></td>
      <td className="govuk-table__cell"></td>
      <td className="govuk-table__cell"></td>
    </tr>
  );
}

function TableRowFolder(props) {
  const folderName = prefixToFolder(props.folder.Prefix);
  const folder = props.folder;
  return (
    <tr className="govuk-table__row pointer" onClick={() => props.onFolderSelect(folder, !folder.isSelected)}>
      <td className="govuk-table__cell govuk-table__cell--checkbox">
        <div className="govuk-form-group">
          <div className="govuk-checkboxes--small">
            <div className="govuk-checkboxes__item">
              <div>
                <input
                  className="govuk-checkboxes__input"
                  type="checkbox"
                  checked={folder.isSelected}
                  onChange={(e) =>
                    props.onFolderSelect(folder, e.target.checked)
                  }
                />
                <label className="govuk-label govuk-checkboxes__label"></label>
              </div>
            </div>
          </div>
        </div>
      </td>
      <td className="govuk-table__cell">
        <a
          className="folder govuk-link govuk-link--no-visited"
          onClick={(e) => {
            e.preventDefault();
            props.onClick();
          }}
          href="#"
        >
          {folderName}
        </a>
      </td>
      <td className="govuk-table__cell"></td>
      <td className="govuk-table__cell"></td>
      <td className="govuk-table__cell" style={{ width: "8em" }}></td>
    </tr>
  );
}

function TableRowFile(props) {
  let createTableButton = null;
  const file = props.file;
  const filename = fullPathToFilename(file.Key);

  if (file.Key.substr(file.Key.length - 3, file.Key.length) === "csv") {
    const createTableUrl = `${props.createTableUrl}?path=${file.Key}`;
    createTableButton = (
      <a
        className="create-table govuk-link govuk-link--no-visited"
        href={createTableUrl}
      >
        Create table
      </a>
    );
  }

  return (
    <tr className="govuk-table__row pointer" onClick={() => props.onFileSelect(file, !file.isSelected)}>
      <td className="govuk-table__cell govuk-table__cell--checkbox">
        <div className="govuk-form-group">
          <div className="govuk-checkboxes--small">
            <div className="govuk-checkboxes__item">
              <input
                className="govuk-checkboxes__input"
                type="checkbox"
                checked={file.isSelected}
                onChange={(e) => props.onFileSelect(file, e.target.checked)}
              />
              <label className="govuk-label govuk-checkboxes__label"></label>
            </div>
          </div>
        </div>
      </td>
      <td className="govuk-table__cell">
        <a
          className="file govuk-link govuk-link--no-visited"
          onClick={(e) => {
            e.preventDefault();
            props.onFileClick(file.Key);
          }}
          href="#"
        >
          {filename}
        </a>
      </td>
      <td className="govuk-table__cell govuk-table__cell--numeric">
        {file.formattedDate.toLocaleString()}
      </td>
      <td className="govuk-table__cell govuk-table__cell--numeric">
        {bytesToSize(file.Size)}
      </td>
      <td className="govuk-table__cell govuk-table__cell--numeric">
        {createTableButton}
      </td>
    </tr>
  );
}

export class FileList extends React.Component {
  constructor(props) {
    super(props);
  }

  render() {
    const files = this.props.files;
    const folders = this.props.folders;
    return (
      <table className="govuk-table" style={{ tableLayout: "fixed" }}>
        <thead>
          <TableHeader />
        </thead>
        <tbody>
          {folders.map((folder) => {
            if (folder.isBigData)
              return (
                <TableRowBigDataFolder
                  key={folder.Prefix}
                  folder={folder}
                  onClick={() => this.props.onFolderClick(folder.Prefix)}
                />
              );
            else
              return (
                <TableRowFolder
                  key={folder.Prefix}
                  folder={folder}
                  onClick={() => this.props.onFolderClick(folder.Prefix)}
                  onFolderSelect={this.props.onFolderSelect}
                />
              );
          })}
          {files.map((file) => {
            return (
              <TableRowFile
                key={file.Key}
                file={file}
                createTableUrl={this.props.createTableUrl}
                onFileClick={() => this.props.onFileClick(file.Key)}
                onFileSelect={this.props.onFileSelect}
              />
            );
          })}
        </tbody>
      </table>
    );
  }
}
