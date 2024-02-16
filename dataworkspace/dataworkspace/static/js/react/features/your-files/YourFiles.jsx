import React, { useEffect, useRef, useState } from 'react';

import AWS from 'aws-sdk';

import AddFolderPopup from './components/AddFolderModal';
import BigDataMessage from './components/BigDataMessage';
import DeleteObjectsPopup from './components/DeleteObjectsModal';
import ErrorModal from './components/ErrorModal';
import FileList from './components/FileList';
import Header from './components/Header';
import TeamsPrefixMessage from './components/TeamsPrefixMessage';
import UploadFilesPopup from './components/UploadFilesModal';
import { getBreadcrumbs, getFolderName } from './utils';
import Credentials from './utils/Credentials';

import './App.scss';

const popupTypes = {
  ADD_FOLDER: 'addFolder',
  UPLOAD_FILES: 'uploadFiles',
  DELETE_OBJECTS: 'deleteObjects',
};

const YourFiles = (props) => {
    const appConfig = props.config;
    const [s3, setS3] = useState(null);
    const [files, setFiles] = useState([]);
    const [folders, setFolders] = useState([]);
    const [selectedFiles, setSelectedFiles] = useState([]);
    const [foldersToDelete, setFoldersToDelete] = useState([]);
    const [currentPrefix, setCurrentPrefix] = useState(
        appConfig.initialPrefix.replace(/^\//, "").replace(/([^\/]$)/, "$1/")
    );
    const [bigDataFolder, setBigDataFolder] = useState(appConfig.bigdataPrefix);
    const [createTableUrl, setCreateTableUrl] = useState(appConfig.createTableUrl);
    const [isLoaded, setIsLoaded] = useState(false);
    const [error, setError] = useState(null);
    const [bucketName, setBucketName] = useState(appConfig.bucketName);
    const [region, setRegion] = useState(appConfig.region);
    const [showBigDataMessage, setShowBigDataMessage] = useState(false);
    const [popups, setPopups] = useState(
        Object.fromEntries(
            Object.entries(popupTypes).map((key, value) => [value, false])
        )
    );
    const [dragActive, setDragActive] = useState(false);

    const fileInputRef = useRef(null);

    useEffect(() => {
        const awsConfig = {
            credentials: new Credentials(appConfig.credentialsUrl),
            region: appConfig.region,
            s3ForcePathStyle: true,
            ...(appConfig.endpointUrl ? { endpoint: appConfig.endpointUrl } : {}),
            httpOptions: {
              timeout: 10 * 60 * 60 * 1000
            }
        };

        setS3(new AWS.S3(awsConfig));
    });

    useEffect(() => {
        const handlePopState = (event) => {
            setCurrentPrefix(
                event.state && event.state.prefix
                    ? event.state.prefix
                    : props.config.initialPrefix
            );
            refresh();
        };

        window.addEventListener('popstate', handlePopState);

        return () => {
            window.removeEventListener('popstate', handlePopState);
        };
    }, []);

    const onFileChange = (event) => {
        if (!event.target.files) {
            return;
        }

        const files = [];

        for (let i = 0; i < event.target.files.length; i++) {
            const file = event.target.files[i];
            file.relativePath = file.name;
            files.push(file);
        }

        setSelectedFiles(files);
        showPopup(popupTypes.UPLOAD_FILES);
        fileInputRef.current.value = null;
    };

    return (
        <></>
    );
};

export default YourFiles;