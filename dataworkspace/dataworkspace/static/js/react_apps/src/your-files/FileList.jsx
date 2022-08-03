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

function TableHeader(props) {
  return (
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
        <TableHeader />
        <tbody>
          {folders.map((folder) => {
            return (
              <tr key={folder.Prefix}>
                <td className="govuk-table__cell govuk-table__cell--checkbox">
                  <div className="govuk-form-group">
                    <div className="govuk-checkboxes--small">
                      <div className="govuk-checkboxes__item">
                        {folder.isBigData ? (
                          <svg
                            aria-hidden="true"
                            focusable="false"
                            data-prefix="fas"
                            data-icon="database"
                            className="svg-inline--fa fa-database fa-w-14"
                            role="img"
                            xmlns="http://www.w3.org/2000/svg"
                            viewBox="0 0 448 512"
                            style={{
                              marginTop: "10px",
                              height: "24px",
                              marginLeft: "2px",
                            }}
                            width="21"
                            height="24"
                          >
                            <path
                              fill="currentColor"
                              d="M448 73.143v45.714C448 159.143 347.667 192 224 192S0 159.143 0 118.857V73.143C0 32.857 100.333 0 224 0s224 32.857 224 73.143zM448 176v102.857C448 319.143 347.667 352 224 352S0 319.143 0 278.857V176c48.125 33.143 136.208 48.572 224 48.572S399.874 209.143 448 176zm0 160v102.857C448 479.143 347.667 512 224 512S0 479.143 0 438.857V336c48.125 33.143 136.208 48.572 224 48.572S399.874 369.143 448 336z"
                            ></path>
                          </svg>
                        ) : (
                          <div>
                            <input
                              className="govuk-checkboxes__input"
                              type="checkbox"
                            />
                            <label className="govuk-label govuk-checkboxes__label"></label>
                          </div>
                        )}
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
