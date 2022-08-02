import React from "react";
import "./FileList.css";

const sizes = ["bytes", "KB", "MB", "GB", "TB"];

function bytesToSize(bytes) {
  if (bytes === 0) return "0 bytes";
  const ii = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10);
  return `${Math.round(bytes / 1024 ** ii, 2)} ${sizes[ii]}`;
}

// Convert cars/vw/golf.png to golf.png
function fullpath2filename(path) {
  return path.replace(/^.*[\\/]/, "");
}

// Convert cars/vw/ to vw/
function prefix2folder(prefix) {
  const parts = prefix.split("/");
  return `${parts[parts.length - 2]}/`;
}

function Folder(props) {
  const folderName = prefix2folder(props.text);
  return (
    <a className="folder govuk-link" onClick={props.onClick}>
      {folderName}
    </a>
  );
}

function File(props) {
  const filename = fullpath2filename(props.text);
  return (
    <a className="file govuk-link" onClick={props.onClick}>
      {filename}
    </a>
  );
}

export class FileList extends React.Component {
  constructor(props) {
    super(props);

    this.handleFolderClick = this.handleFolderClick.bind(this);
    this.handleFileClick = this.props.onFileClick.bind(this);
    this.handleCreateTableClick = this.handleCreateTableClick.bind(this);
  }

  async componentDidMount() {
    console.log("componentDidMount filelist");
    console.log(this.props.files);
  }

  async componentDidUpdate() {
    console.log("componentDidUpdate");
  }

  handleFolderClick(prefix) {
    console.log("handleFolderClick", prefix);
    this.props.onFolderClick(prefix);
    e.preventDefault();
  }

  handleFileClick(key) {
    console.log("fileClick", key);
  }

  // This is a specific case for data-workspace
  // probably extract this to an open-link type effect
  handleCreateTableClick(key) {
    console.log("createTable", key);
  }

  render() {
    const files = this.props.files;
    const folders = this.props.folders;
    return (
      <table className="govuk-table">
        <thead>
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
        </thead>
        <tbody>
          {folders.map((folder) => {
            return (
              <tr key={folder.Prefix}>
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
                  <Folder
                    text={folder.Prefix}
                    onClick={() => this.handleFolderClick(folder.Prefix)}
                  />
                </td>
                <td className="govuk-table__cell"></td>
                <td className="govuk-table__cell"></td>
                <td className="govuk-table__cell" style={{ width: "8em" }}></td>
              </tr>
            );
          })}

          {files.map((file) => {
            let createTableButton = null;
            console.log(file);
            if (file.isCsv) {
              createTableButton = (
                <a
                  className="create-table govuk-link"
                  onClick={() => this.handleCreateTableClick(file.Key)}
                >
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
                <td className="govuk-table__cell govuk-table__cell--numeric">
                  {createTableButton}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    );
  }
}
