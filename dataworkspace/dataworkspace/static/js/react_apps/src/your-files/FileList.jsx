import React from "react";
import "./FileList.css";

import { prefixToFolder, bytesToSize, fullPathToFilename } from "./utils";

function BigDataFolder(props) {
  const folderName = prefixToFolder(props.folder.Prefix);
  return (
    <tr key={props.folder.Prefix} className="govuk-table__row">
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
          className="govuk-link govuk-link--no-visited"
          onClick={props.onClick}
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

function Folder(props) {
  const folderName = prefixToFolder(props.folder.Prefix);
  return (
    <tr key={props.folder.Prefix} className="govuk-table__row">
      <td className="govuk-table__cell govuk-table__cell--checkbox">
        <div className="govuk-form-group">
          <div className="govuk-checkboxes--small">
            <div className="govuk-checkboxes__item">
              <div>
                <input className="govuk-checkboxes__input" type="checkbox" />
                <label className="govuk-label govuk-checkboxes__label"></label>
              </div>
            </div>
          </div>
        </div>
      </td>
      <td className="govuk-table__cell">
        <a className="folder govuk-link" onClick={props.onClick}>
          {folderName}
        </a>
      </td>
      <td className="govuk-table__cell"></td>
      <td className="govuk-table__cell"></td>
      <td className="govuk-table__cell" style={{ width: "8em" }}></td>
    </tr>
  );
}

function File(props) {
  const filename = fullPathToFilename(props.text);
  return (
    <a className="file govuk-link" onClick={props.onClick}>
      {filename}
    </a>
  );
}

function TableHeader(props) {
  return (
    <tr className="govuk-table__row">
      <td className="govuk-table__header govuk-table__header--checkbox"></td>

      <th scope="col" className="govuk-table__header">
        Name
      </th>
      <th scope="col" className="govuk-table__header">
        Last modified
      </th>
      <th scope="col" className="govuk-table__header">
        Size
      </th>
      <th scope="col" className="govuk-table__header">
        Details
      </th>
    </tr>
  );
}

export class FileList extends React.Component {
  constructor(props) {
    super(props);

    this.handleFolderClick = this.props.onFolderClick.bind(this);
    this.handleFileClick = this.props.onFileClick.bind(this);
    this.handleCreateTableClick = this.props.onCreateTableClick.bind(this);
  }

  async componentDidMount() {
    console.log("componentDidMount filelist");
    console.log(this.props.files);
  }

  async componentDidUpdate() {
    console.log("componentDidUpdate");
  }

  render() {
    const files = this.props.files;
    const folders = this.props.folders;
    return (
      <table className="govuk-table">
        <thead>
          <TableHeader />
        </thead>
        <tbody>
          {folders.map((folder) => {
            if (folder.isBigData)
              return (
                <BigDataFolder
                  folder={folder}
                  onClick={() => this.handleFolderClick(folder.Prefix)}
                />
              );
            else
              return (
                <Folder
                  folder={folder}
                  onClick={() => this.handleFolderClick(folder.Prefix)}
                />
              );
          })}
          {files.map((file) => {
            let createTableButton = null;
            console.log(file);
            if (file.isCsv) {
              const createTableUrl = `${YOURFILES_CONFIG.createTableUrl}?path=${file.Key}`;
              createTableButton = (
                <a className="create-table govuk-link" href={createTableUrl}>
                  Create table
                </a>
              );
            }
            return (
              <tr key={file.Key}>
                <td className="govuk-table__cell govuk-table__cell--checkbox">
                  <div className="govuk-form-group">
                    <div className="govuk-checkboxes--small">
                      <div className="govuk-checkboxes__item">
                        <input
                          className="govuk-checkboxes__input"
                          type="checkbox"
                        />
                        <label className="govuk-label govuk-checkboxes__label"></label>
                      </div>
                    </div>
                  </div>
                </td>
                <td className="govuk-table__cell">
                  <File
                    text={file.Key}
                    onClick={() => this.handleFileClick(file.Key)}
                  />
                </td>
                <td className="govuk-table__cell govuk-table__cell--numeric">
                  {file.formattedDate.toLocaleString()}
                </td>
                <td className="govuk-table__cell govuk-table__cell--numeric">
                  {bytesToSize(file.Size)}
                </td>
                <td className="govuk-table__cell">{createTableButton}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
}
