import React from "react";
import "./FileList.css";

import { prefixToFolder, bytesToSize, fullPathToFilename } from "../../utils";

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
        className="govuk-table__header"
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
      <td className="govuk-table__cell govuk-table__cell--word-wrapper">
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

function TableRowSharedFolder(props) {
  const folderName = prefixToFolder(props.folder.Prefix);
  return (
    <tr className="govuk-table__row">
      <td
        className="govuk-table__cell govuk-table__cell--checkbox"
        title="This folder cannot be deleted"
      >
          <svg version="1.1" id="Layer_1" xmlns="http://www.w3.org/2000/svg"
               x="0px" y="0px"
               width="80%" viewBox="0 0 400 400" enable-background="new 0 0 400 400"
               style={{marginLeft: "-4px", marginTop: "7px", height: "30px"}}>
<path fill="#FEFEFE" opacity="1.000000" stroke="none"
      d="
M1.000000,149.000000
	C1.000000,99.348694 1.000000,50.197392 1.000000,1.023043
	C134.276306,1.023043 267.552643,1.023043 400.914490,1.023043
	C400.914490,134.234604 400.914490,267.469269 400.914490,400.851990
	C267.666779,400.851990 134.333420,400.851990 1.000000,400.851990
	C1.000000,317.114105 1.000000,233.307053 1.000000,149.000000
M330.499756,375.620758
	C346.829956,375.620758 363.160248,375.645264 379.490356,375.609619
	C386.851654,375.593536 389.979431,372.624390 389.981537,365.442352
	C390.008698,273.124939 390.143555,180.807144 389.911224,88.490318
	C389.842041,60.995514 366.435394,46.064514 347.754425,46.642120
	C322.782593,47.414238 297.768951,46.833019 272.773254,46.833126
	C261.775146,46.833176 250.777008,46.852341 239.778976,46.824715
	C235.304367,46.813477 232.501694,48.863743 231.901337,53.343231
	C231.075256,59.507065 234.317398,63.019737 240.751022,63.023434
	C275.744995,63.043533 310.738983,63.009411 345.732819,63.075512
	C348.693054,63.081104 351.734039,63.358219 354.597260,64.071800
	C365.569824,66.806412 374.015564,77.992943 372.333801,87.644501
	C363.027618,81.028839 352.585052,79.806786 341.553650,79.872276
	C301.228668,80.111702 260.901428,79.967010 220.575058,79.967010
	C218.804901,79.967010 217.034744,79.967010 214.999573,79.967010
	C214.999573,75.122726 215.009140,70.815552 214.997955,66.508438
	C214.940262,44.269337 197.911896,26.177160 175.676025,25.983925
	C134.854919,25.629177 94.025795,25.663500 53.204830,26.047737
	C31.959282,26.247715 14.969735,44.234421 14.968859,65.326912
	C14.964725,164.809753 14.966973,264.292603 14.967052,363.775452
	C14.967060,373.577026 17.047764,375.620056 27.051868,375.620178
	C127.867821,375.621155 228.683777,375.620758 330.499756,375.620758
z"/>
              <path fill="#010101" opacity="1.000000" stroke="none"
                    d="
M329.999756,375.620758
	C228.683777,375.620758 127.867821,375.621155 27.051868,375.620178
	C17.047764,375.620056 14.967060,373.577026 14.967052,363.775452
	C14.966973,264.292603 14.964725,164.809753 14.968859,65.326912
	C14.969735,44.234421 31.959282,26.247715 53.204830,26.047737
	C94.025795,25.663500 134.854919,25.629177 175.676025,25.983925
	C197.911896,26.177160 214.940262,44.269337 214.997955,66.508438
	C215.009140,70.815552 214.999573,75.122726 214.999573,79.967010
	C217.034744,79.967010 218.804901,79.967010 220.575058,79.967010
	C260.901428,79.967010 301.228668,80.111702 341.553650,79.872276
	C352.585052,79.806786 363.027618,81.028839 372.333801,87.644501
	C374.015564,77.992943 365.569824,66.806412 354.597260,64.071800
	C351.734039,63.358219 348.693054,63.081104 345.732819,63.075512
	C310.738983,63.009411 275.744995,63.043533 240.751022,63.023434
	C234.317398,63.019737 231.075256,59.507065 231.901337,53.343231
	C232.501694,48.863743 235.304367,46.813477 239.778976,46.824715
	C250.777008,46.852341 261.775146,46.833176 272.773254,46.833126
	C297.768951,46.833019 322.782593,47.414238 347.754425,46.642120
	C366.435394,46.064514 389.842041,60.995514 389.911224,88.490318
	C390.143555,180.807144 390.008698,273.124939 389.981537,365.442352
	C389.979431,372.624390 386.851654,375.593536 379.490356,375.609619
	C363.160248,375.645264 346.829956,375.620758 329.999756,375.620758
M143.550705,268.134583
	C138.577469,276.757874 136.116165,286.083496 135.631393,295.994141
	C135.155350,305.726074 141.864670,312.987244 151.549469,312.992676
	C185.519196,313.011810 219.488953,313.015289 253.458649,312.989532
	C262.145599,312.982941 269.076172,306.288879 268.919373,297.619843
	C268.492157,273.999603 257.477264,256.615631 237.118988,245.024185
	C224.298676,237.724640 210.176498,237.651550 196.008804,238.031158
	C173.429291,238.636124 155.915405,248.163132 143.550705,268.134583
M322.498108,294.967804
	C327.324768,294.966980 332.157837,295.125275 336.976715,294.930939
	C345.925079,294.570007 352.705841,287.608612 352.321167,278.703827
	C351.305267,255.189667 339.977783,238.306503 318.756439,228.210251
	C306.269928,222.269684 292.863617,223.440033 279.621796,223.856018
	C271.739655,224.103638 264.373230,226.303818 257.557129,230.371155
	C267.307404,249.988907 277.098969,269.328461 286.494202,288.858643
	C288.717194,293.479614 291.881958,295.010315 296.533600,294.982056
	C304.855103,294.931519 313.177124,294.967804 322.498108,294.967804
M175.851868,214.652435
	C191.452423,229.510117 214.162537,229.479782 228.981094,214.581497
	C243.481293,200.003265 243.509430,176.287491 229.043869,161.662811
	C214.848801,147.311646 191.047592,146.996277 176.475922,160.966309
	C161.321152,175.495331 160.835693,198.320526 175.851868,214.652435
M322.941284,176.031174
	C322.961395,174.366333 323.000488,172.701462 322.998657,171.036636
	C322.979828,153.877197 309.274109,139.300873 292.038269,138.102112
	C269.752899,136.552155 251.960648,157.704849 257.336884,179.357544
	C261.801575,197.338928 280.111603,208.607147 297.919922,203.820709
	C311.654602,200.129181 319.781403,190.727692 322.941284,176.031174
z"/>
              <path fill="#FEFEFE" opacity="1.000000" stroke="none"
                    d="
M143.764099,267.832886
	C155.915405,248.163132 173.429291,238.636124 196.008804,238.031158
	C210.176498,237.651550 224.298676,237.724640 237.118988,245.024185
	C257.477264,256.615631 268.492157,273.999603 268.919373,297.619843
	C269.076172,306.288879 262.145599,312.982941 253.458649,312.989532
	C219.488953,313.015289 185.519196,313.011810 151.549469,312.992676
	C141.864670,312.987244 135.155350,305.726074 135.631393,295.994141
	C136.116165,286.083496 138.577469,276.757874 143.764099,267.832886
z"/>
              <path fill="#FEFEFE" opacity="1.000000" stroke="none"
                    d="
M321.998535,294.967804
	C313.177124,294.967804 304.855103,294.931519 296.533600,294.982056
	C291.881958,295.010315 288.717194,293.479614 286.494202,288.858643
	C277.098969,269.328461 267.307404,249.988907 257.557129,230.371155
	C264.373230,226.303818 271.739655,224.103638 279.621796,223.856018
	C292.863617,223.440033 306.269928,222.269684 318.756439,228.210251
	C339.977783,238.306503 351.305267,255.189667 352.321167,278.703827
	C352.705841,287.608612 345.925079,294.570007 336.976715,294.930939
	C332.157837,295.125275 327.324768,294.966980 321.998535,294.967804
z"/>
              <path fill="#FEFEFE" opacity="1.000000" stroke="none"
                    d="
M175.598373,214.399170
	C160.835693,198.320526 161.321152,175.495331 176.475922,160.966309
	C191.047592,146.996277 214.848801,147.311646 229.043869,161.662811
	C243.509430,176.287491 243.481293,200.003265 228.981094,214.581497
	C214.162537,229.479782 191.452423,229.510117 175.598373,214.399170
z"/>
              <path fill="#FDFDFD" opacity="1.000000" stroke="none"
                    d="
M322.909729,176.471893
	C319.781403,190.727692 311.654602,200.129181 297.919922,203.820709
	C280.111603,208.607147 261.801575,197.338928 257.336884,179.357544
	C251.960648,157.704849 269.752899,136.552155 292.038269,138.102112
	C309.274109,139.300873 322.979828,153.877197 322.998657,171.036636
	C323.000488,172.701462 322.961395,174.366333 322.909729,176.471893
z"/>
</svg>
      </td>
      <td className="govuk-table__cell govuk-table__cell--word-wrapper">
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
        <div className="govuk-form-group" style={{ marginBottom: "0" }}>
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
      <td className="govuk-table__cell govuk-table__cell--word-wrapper">
        <a
          className="folder govuk-link govuk-link--no-visited"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
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

  if (file.Key.substr(file.Key.length - 4, file.Key.length) === ".csv") {
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
        <div className="govuk-form-group" style={{ marginBottom: "0" }}>
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
      <td className="govuk-table__cell govuk-table__cell--word-wrapper">
        <a
          className="file govuk-link govuk-link--no-visited"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            props.onFileClick(file.Key);
          }}
          href="#"
        >
          {filename}
        </a>
      </td>
      <td className="govuk-table__cell">
        {file.formattedDate.toLocaleString()}
      </td>
      <td className="govuk-table__cell">
        {bytesToSize(file.Size)}
      </td>
      <td className="govuk-table__cell">
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
            if (folder.isSharedFolder)
              return (
                <TableRowSharedFolder
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
