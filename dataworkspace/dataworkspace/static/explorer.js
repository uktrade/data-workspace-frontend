// Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License").
//
// You may not use this file except in compliance with the License. A copy
// of the License is located at
//
// http://aws.amazon.com/apache2.0/
//
// or in the "license" file accompanying this file. This file is distributed
// on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND,
// either express or implied. See the License for the specific language governing
// permissions and limitations under the License.
//
// Modified by the Department for International Trade

angular.module('aws-js-s3-explorer', []);

angular.module('aws-js-s3-explorer').factory('s3', (Config) => {
    function fetchJSON(url) {
        return new Promise((resolve, reject) => {
          function resolveJSON() {
            resolve(JSON.parse(oReq.responseText));
          }

          var oReq = new XMLHttpRequest();
          oReq.addEventListener('load', resolveJSON);
          oReq.addEventListener('error', reject);
          oReq.open('GET', url);
          oReq.send();
        });
      }

    class Credentials extends AWS.Credentials {
        constructor() {
            super();
            this.expiration = 0;
        }

        async refresh(callback) {
            try {
                var response = await fetchJSON(Config.credentialsUrl);
            } catch(err) {
                callback(err);
                return
            }
            this.accessKeyId = response.AccessKeyId;
            this.secretAccessKey = response.SecretAccessKey;
            this.sessionToken = response.SessionToken;
            this.expiration = Date.parse(response.Expiration);
            callback();
        }

        needsRefresh() {
            return this.expiration - 60 < Date.now();
        }
    }

    AWS.config.update({
        credentials: new Credentials(),
        region: Config.region
    });
    return new AWS.S3({s3ForcePathStyle: true });
});

angular.module('aws-js-s3-explorer').run(($rootScope) => {
    const sizes = ['bytes', 'KB', 'MB', 'GB', 'TB'];

    $rootScope.bytesToSize = (bytes) => {
        if (bytes === 0) return '0 bytes';
        const ii = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10);
        return `${Math.round(bytes / (1024 ** ii), 2)} ${sizes[ii]}`;
    }

    // Convert cars/vw/golf.png to golf.png
    $rootScope.fullpath2filename = (path) => {
        return path.replace(/^.*[\\/]/, '');
    }

    // Convert cars/vw/ to vw/
    $rootScope.prefix2folder = (prefix) => {
        const parts = prefix.split('/');
        return `${parts[parts.length - 2]}/`;
    }
});

angular.module('aws-js-s3-explorer').controller('ViewController', (Config, s3, $rootScope, $scope) => {
    function startsWith(string, search) {
        return string.substring(0, search.length) === search;
    }

    var originalPrefix = Config.prefix;
    var currentPrefix = Config.prefix;

    $scope.breadcrumbs = [];
    $scope.bigdataPrefix = Config.bigdataPrefix;
    $scope.bigdata = null;
    $scope.inBigdata = false;
    $scope.prefixes = [];
    $scope.objects = [];
    $scope.initialising = true;

    $scope.setCurrentPrefix = (prefix, $event) => {
        $event.stopPropagation();
        currentPrefix = prefix;
        listObjects();
        setBreadcrumbs();
    };

    $scope.numSelected = () => {
        var numSelected = 0;
        var i;
        for (i = 0; i < $scope.prefixes.length; i++) {
            if ($scope.prefixes[i].selected) {
                ++numSelected;
            }
        }
        for (i = 0; i < $scope.objects.length; i++) {
            if ($scope.objects[i].selected) {
                ++numSelected;
            }
        }
        return numSelected;
    }

    $scope.toggleSelected = (item) => {
        item.selected = !item.selected;
    };

    $scope.download = async (key, $event) => {
        $event.stopPropagation();
        const params = {
           Bucket: Config.bucket,
           Key: key,
           Expires: 15,
           ResponseContentDisposition: 'attachment',
        }
        try {
            url = await s3.getSignedUrlPromise('getObject', params);
        } catch (err) {
            $scope.$apply(() => {
                $rootScope.$broadcast('error', { params, err });
            });
            return;
        }
        window.location.href = url;
    }

    var setBreadcrumbs = () => {
        var prefix = Config.prefix;
        $scope.breadcrumbs = [{
            prefix: prefix,
            label: 'home'
        }];
        var labels = currentPrefix.substring(prefix.length).split('/');
        for (let i = 0; i < labels.length - 1; ++i) {
            prefix += (labels[i] + '/');
            $scope.breadcrumbs.push({
                prefix: prefix,
                label: labels[i]
            });
        }
    }

    $scope.$on('reload-object-list', () => {
        listObjects();
    });

    $scope.listObjects = () => {
        $scope.$broadcast('spinner::start::refresh');
        listObjects();
    }

    var listObjects = async () => {
        // This is an async function, so copy variables that could change during to avoid
        // future gotchas
        var prefix = currentPrefix;
        var bucket = Config.bucket;
        const params = {
            Bucket: bucket, Prefix: prefix, Delimiter: '/'
        };
        try {
            response = await s3.listObjectsV2(params).promise();
            $scope.$apply(function () {
                $scope.bigdata = prefix == originalPrefix ? {
                    Prefix: originalPrefix + Config.bigdataPrefix
                } : null;
                $scope.prefixes = response.CommonPrefixes.filter((prefix) => {
                    return prefix.Prefix != originalPrefix + Config.bigdataPrefix;
                });
                $scope.objects = response.Contents.filter((object) => {
                    return object.Key != prefix;
                }).map(object => {
                    object.isCsv = object.Key.substr(object.Key.length - 3, object.Key.length) === 'csv';
                    return object;
                });
                $scope.initialising = false;
                $scope.inBigdata = startsWith(currentPrefix, originalPrefix + Config.bigdataPrefix);
            });
        } catch (err) {
            $scope.$apply(() => {
                $rootScope.$broadcast('error', { params, err });
            });
        }
    };

    $scope.openAddFolderModal = () => {
        $rootScope.$broadcast('modal::open::add-folder', { bucket: Config.bucket, currentPrefix });
    };

    $scope.filesSelected = (files) => {
        $rootScope.$broadcast('modal::open::upload', {bucket: Config.bucket, originalPrefix, currentPrefix, files});
    }

    $scope.$on('dropzone::files', (e, files) => {
        $rootScope.$broadcast('modal::open::upload', {bucket: Config.bucket, originalPrefix, currentPrefix, files});
    });

    $scope.openFileBrowser = () => {
        $scope.$broadcast('open-file-browser');
    };

    $scope.openTrashModal = () => {
        var prefixes = $scope.prefixes.filter((prefix) => prefix.selected);
        var objects = $scope.objects.filter((object) => object.selected);
        $rootScope.$broadcast('modal::open::trash', { bucket: Config.bucket, prefixes, objects });
    };

    listObjects();
    setBreadcrumbs();
});

angular.module('aws-js-s3-explorer').controller('AddFolderController', (s3, $scope, $rootScope) => {
    $scope.$on('modal::open::add-folder', (e, args) => {
        $scope.model = {
            bucket: args.bucket,
            currentPrefix: args.currentPrefix,
            newFolder: ''
        };
    });

    $scope.addFolder = async () => {
        const withoutLeadTrailSlash = $scope.model.newFolder.replace(/^\/+/g, '').replace(/\/+$/g, '');
        const folder = $scope.model.currentPrefix + withoutLeadTrailSlash + '/';
        const params = { Bucket: $scope.model.bucket, Key: folder };
        var canCreate = false;

        // Slightly awkward since a 404 is converted to an exception
        try {
            await s3.headObject(params).promise();
        } catch (err) {
            canCreate = (err.code === 'NotFound');
            if (!canCreate) {
                alert('Error creating folder: ' + err);
                return;
            }
        }
        if (!canCreate) {
            alert('Error: folder or object already exists at ' + params.Key);
            return;
        }

        try {
            await s3.putObject(params).promise();
        } catch (err) {
            alert('Error creating folder: ' + err);
        }
        $scope.$broadcast('modal::close::add-folder');
        $rootScope.$broadcast('reload-object-list');
        $scope.model.newFolder = '';
    };
});

angular.module('aws-js-s3-explorer').controller('UploadController', (s3, $scope, $rootScope) => {
    function queue(concurrency) {
        var running = 0;
        const tasks = [];

        return async function run(task) {
            tasks.push(task);
            if (running >= concurrency) return;

            ++running;
            while (tasks.length) {
                try {
                    await tasks.shift()();
                } catch(err) {
                    console.error(err);
                }
            }
            --running;
        }
    }

    $scope.$on('modal::open::upload', (e, args) => {
        // If we start all uploads at once, the browser attempts to start at
        // least one connection per file. This means:
        // - later S3 uploads will timeout, since they won't even start since
        //   earlier uploads take all the browser connections;
        // - or, in higher number of files, later uploads to fail immediately
        //   with a network error, since the browser limits how many
        //   connections can be queued.
        // So we
        // - make sure that any file that has its upload initiated would be
        //   able to use at least one connection;
        // - try make sure that in most situations maxConnections connections
        //   will be used. To get maxConnections used in all situations
        //   would be more complicated: KISS
        const maxConnections = 4;
        const concurrentFiles = Math.min(maxConnections, args.files.length);
        const connectionsPerFile = Math.floor(maxConnections / concurrentFiles);

        var folder = args.currentPrefix.substring(args.originalPrefix.length);
        $scope.model = {
            bucket: args.bucket,
            folder: folder == '' ? 'home/' : $scope.prefix2folder(folder),
            currentPrefix: args.currentPrefix,
            files: args.files,
            remaining: args.files.length,
            uploading: false,
            aborted: false,
            queue: queue(concurrentFiles),
            connectionsPerFile: connectionsPerFile,
            uploads: []
        };
    });
    $scope.$on('modal::close::upload', () => {
        $scope.model.aborted = true;
        $scope.model.uploads.forEach((upload) => {
            upload.abort();
        });
    });
    $scope.$on('modal::close-end::upload', (e, args) => {
        $scope.model.uploads = [];
        $scope.model.files = [];
    });

    $scope.uploadFiles = () => {
        $scope.model.uploading = true;

        $scope.model.files.forEach((file) => {
            // If things are horribly slow and the user is quick, we could have opened a "new"
            // model from the point of view of the user, but still in the process of the abort
            // of the old, and so we ensure to only modify the original model
            var model = $scope.model;

            const params = {
                Bucket: model.bucket,
                Key: model.currentPrefix + file.relativePath,
                ContentType: file.type,
                Body: file
            };
            const onProgress = (evt) => {
                const pc = evt.total ? ((evt.loaded * 100.0) / evt.total) : 0;
                const pct = Math.round(pc);
                $scope.$apply(() => {
                    file.progress = pct;
                });
            };
            model.queue(async () => {
                try {
                    if (!model.aborted) {
                        let upload = s3.upload(params, {queueSize: model.connectionsPerFile});
                        model.uploads.push(upload);
                        await upload
                            .on('httpUploadProgress', onProgress)
                            .promise();
                    }
                } catch(err) {
                    if (!model.aborted) {
                        console.error(err);
                        $scope.$apply(() => {
                            file.error = err.code || err.message || err;
                        });
                    }
                } finally {
                    --model.remaining;
                }

                if (model.remaining == 0) {
                    $scope.$apply();
                    $rootScope.$broadcast('reload-object-list');
                }
            });
        });
    };
});

angular.module('aws-js-s3-explorer').controller('ErrorController', ($scope) => {
    // Not using Object.entries for IE11 support
    function objEntries(obj) {
        var ownProps = Object.keys(obj);
        var i = ownProps.length;
        var resArray = new Array(i);
        while (i--) resArray[i] = [ownProps[i], obj[ownProps[i]]];
        return resArray;
    }

    $scope.$on('error', (e, args) => {
        const { params, err } = args;

        const message = err && 'message' in err ? err.message : '';
        const code = err && 'code' in err ? err.code : '';
        const errors = objEntries(err || {}).map(([key, value]) => ({ key, value }));

        $scope.error = { params, message, code, errors };
        $scope.$broadcast('modal::open::error');
    });

    $scope.error = {
        errors: [], message: '',
    };
});

angular.module('aws-js-s3-explorer').controller('TrashController', (s3, $scope, $rootScope) => {
    $scope.$on('modal::open::trash', (e, args) => {
        $scope.model = {
            bucket: args.bucket,
            prefixes: args.prefixes,
            objects: args.objects,
            count: args.prefixes.length + args.objects.length,
            trashing: false,
            aborted: false,
            finished: false           
        };
    });
    $scope.$on('modal::close::trash', (e, args) => {
        $scope.model.aborted = true;
    });
    $scope.$on('modal::close-end::trash', (e, args) => {
        $scope.model.prefixes = [];
        $scope.model.objects = [];
    });

    $scope.deleteFiles = async () => {
        let model = $scope.model;
        model.trashing = true;
        let [scheduleDelete, flushDelete] = Deleter(s3, model.bucket);

        // Slight hack to ensure that we are no longer in a digest, to make
        // each iteration of the below loop able to assume it's not in a digest
        await new Promise((resolve) => window.setTimeout(resolve));

        const setObjectMessage = function(obj, messageKey, messageText) {
            if (!model.aborted) {
                $scope.$apply(() => {
                    obj[messageKey] = messageText;
                });
            }
        }

        // Delete prefixes: fetch all keys under them, deleting as we go to avoid storing in memory
        for (let i = 0; i < model.prefixes.length && !model.aborted; ++i) {
            let prefix = model.prefixes[i];
            setObjectMessage(prefix, 'deleteStarted', true);

            // Attempt to list objects under the prefix. If the list objects
            // call fails, update the model and try the next prefix.
            let continuationToken = null;
            let isTruncated = true;
            while (isTruncated && !model.aborted) {
                let response;
                try {
                    response = await s3.listObjectsV2({
                        Bucket: model.bucket,
                        Prefix: prefix.Prefix,
                        ContinuationToken: continuationToken,
                    }).promise()
                    continuationToken = response.NextContinuationToken;
                    isTruncated = response.IsTruncated;
                } catch (err) {
                    console.error(err);
                    setObjectMessage(prefix, 'deleteError', err.code || err.message || err);
                    continue;
                }

                // Loop through the objects within the prefix and bulk delete them
                for (let j = 0; j < response.Contents.length && !model.aborted; ++j) {
                    try {
                        await scheduleDelete(response.Contents[j].Key);
                    } catch(err) {
                        setObjectMessage(prefix, 'deleteError', err.code || err.message || err);
                        break;
                    }
                }
            }

            try {
                await flushDelete();
            } catch(err) {
                setObjectMessage(prefix, 'deleteError', err.code || err.message || err);
                continue;
            }

            setObjectMessage(prefix, 'deleteFinished', true);
        }

        // Delete objects

        // Find an object by key in the model's list of objects
        const updateObject = function(key, messageKey, message) {
            let objs = model.objects.filter(function (o) {
                return o.Key === key;
            });
            if (objs.length > 0) {
                setObjectMessage(objs[0], messageKey, message);
            }
        }

        // Process the bulk delete response from s3.
        // Sets the `deleteFinished` or `deleteError` attribute accordingly
        const processResponse = function(response) {
            if (typeof response === 'undefined') return;

            // Update objects that were successfully deleted
            for (let i=0; i<response.Deleted.length; i++) {
                updateObject(response.Deleted[i].Key, 'deleteFinished', true);
            }

            // Update objects that had errors
            for (let i=0; i<response.Errors.length; i++) {
                updateObject(response.Errors[i].Key, 'deleteError', response.Errors[i].Code || response.Errors[i].Message);
            }
        }

        for (let i = 0; i < model.objects.length && !model.aborted; ++i) {
            processResponse(await scheduleDelete(model.objects[i].Key));
        }

        processResponse(await flushDelete());

        setObjectMessage($scope.model, 'finished', true);
        $rootScope.$broadcast('reload-object-list');
    };
});

angular.module('aws-js-s3-explorer').directive('modal', () => {
    var backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    document.body.appendChild(backdrop);

    // Without CSS, we don't get transitionend events
    var cssEnabled = window.getComputedStyle(backdrop).getPropertyValue('visibility') == 'hidden';

    return {
        link: function(scope, element, attrs) {
            var name = attrs.modal;
            element[0].addEventListener('click', (event) => {
                event.stopPropagation();
                // Don't close if clicking anywhere inside the modal, e.g. on a button
                if (event.target == element[0]) {
                    close();
                }
            });
            function open() {
                scope.modalVisible = true;
                backdrop.classList.remove('modal-backdrop-out');
                backdrop.classList.add('modal-backdrop-in');
                element[0].classList.remove('modal-out');
                element[0].classList.add('modal-in');
                element[0].removeAttribute('aria-hidden');
                element[0].removeEventListener('transitionend', onCloseEnd);
                element[0].addEventListener('transitionend', onOpenEnd);
                document.addEventListener('keydown', closeIfEscape);

                if (!cssEnabled) broadcastOpenEnd();
            }
            function close() {
                backdrop.classList.remove('modal-backdrop-in');
                backdrop.classList.add('modal-backdrop-out');
                element[0].classList.remove('modal-in');
                element[0].classList.add('modal-out');
                element[0].setAttribute('aria-hidden', 'true');
                document.removeEventListener('keydown', closeIfEscape);
                element[0].removeEventListener('transitionend', onOpenEnd);
                element[0].addEventListener('transitionend', onCloseEnd);

                if (!cssEnabled) hideHtml();
            }
            function closeIfEscape(event) {
                if (event.key === 'Escape') {
                    close();
                }
            }

            // A bit brittle WRT the transitions, but KISS
            function onCloseEnd(e) {
                if (e.propertyName == 'top') {
                    hideHtml();
                    scope.$digest();
                }
            }
            function hideHtml() {
                scope.modalVisible = false;
            }
            function onOpenEnd(e) {
                if (e.propertyName == 'top') {
                    broadcastOpenEnd();
                }
            }
            function broadcastOpenEnd() {
              scope.$broadcast('modal::open-end::' + name);
            }
            scope.$on('modal::open::' + name, open);
            scope.$on('modal::close::' + name, close);
        }
    };
});

angular.module('aws-js-s3-explorer').directive('onFileChange', ($timeout) => {
    return {
        scope: {
            onFileChange: '&'
        },
        link: function(scope, element, attrs) {
            element[0].addEventListener('change', (event) => {
                // Ensure we have an Array
                var files = []
                for (let i = 0; i < event.target.files.length; ++i) {
                    let file = event.target.files[i]
                    // Monkey patch to make the files similar to how they are from drag and drop
                    file.relativePath = file.name;
                    files.push(file);
                }
                // In IE11, we seem to be in a digest, but in Chrome/FF, we're not. So we trigger
                // the callback in a $timeout to safely jump out of a digest if we're in one, and
                // into another. The change happens on a click, so short delay here is fine
                $timeout(function () {
                    scope.onFileChange({files: files});
                });
            });
        }
    };
});

angular.module('aws-js-s3-explorer').directive('triggerClickOn', () => {
    return {
        link: function(scope, element, attrs) {
            scope.$on(attrs.triggerClickOn, () => {
                element[0].click();
            })
        }
    };
});

angular.module('aws-js-s3-explorer').directive('focusOn', () => {
    return {
        link: function(scope, element, attrs) {
            scope.$on(attrs.focusOn, () => {
                element[0].focus();
            })
        }
    };
});

angular.module('aws-js-s3-explorer').directive('dropzone', () => {
    async function entries(directoryReader) {
        var entries = [];
        while (true) {
            var latestEntries = await new Promise((resolve, reject) => {
                directoryReader.readEntries(resolve, reject);
            });
            if (latestEntries.length == 0) break;
            entries = entries.concat(latestEntries);
        }
        return entries;
    }

    async function file(fileEntry) {
        var file = await new Promise((resolve, reject) => {
            fileEntry.file(resolve, reject);
        });
        // We monkey-patch the file to include its FileSystemEntry fullPath,
        // which is a path relative to the root of the pseudo-filesystem of
        // a dropped folder
        file.relativePath = fileEntry.fullPath.substring(1);  // Remove leading slash
        return file;
    }

    async function getFiles(dataTransferItemList) {
        const files = [];
        // DataTransferItemList does not support map
        fileAndDirectoryEntryQueue = [];
        for (let i = 0; i < dataTransferItemList.length; ++i) {
             // At the time of writing no browser supports `getAsEntry`
            fileAndDirectoryEntryQueue.push(dataTransferItemList[i].webkitGetAsEntry());
        }

        while (fileAndDirectoryEntryQueue.length > 0) {
            const entry = fileAndDirectoryEntryQueue.shift();
            if (entry.isFile) {
                files.push(await file(entry));
            } else if (entry.isDirectory) {
                fileAndDirectoryEntryQueue.push(...await entries(entry.createReader()));
            }
        }
        return files;
    }

    return {
        link: function(scope, element, attrs) {
            element[0].classList.add('dropzone');
            element[0].addEventListener('dragover', addClass);
            element[0].addEventListener('dragend', removeClass);
            element[0].addEventListener('dragleave', removeClass);
            element[0].addEventListener('drop', removeClass);
            element[0].addEventListener('drop', broadcastFiles);

            function addClass(event) {
                event.stopPropagation();
                event.preventDefault();
                element[0].classList.add('dragover');
            }
            function removeClass(event) {
                event.stopPropagation();
                event.preventDefault();
                element[0].classList.remove('dragover');
            }
            async function broadcastFiles(event) {
                event.stopPropagation();
                event.preventDefault();

                const files = await getFiles(event.dataTransfer.items);
                scope.$apply(() => {
                    scope.$broadcast('dropzone::files', files);
                }); 
            }
        }
    };
});

angular.module('aws-js-s3-explorer').directive('spinner', () => {
    return {
        link: function(scope, element, attrs) {
            var name = attrs.spinner;

            scope.$on('spinner::start::' + name, () => {
                element[0].classList.add('spin');
            });
            element[0].addEventListener('animationend', () => {
                element[0].classList.remove('spin');
            });
        }
    };
});

function Deleter(s3, bucket) {
    const bulkDeleteMaxFiles = 1000;
    let keys = [];

    async function deleteKeys() {
        let response;
        try {
            response = await s3.deleteObjects({Bucket: bucket, Delete: {Objects: keys}}).promise();
        } catch(err) {
            console.error(err);
            throw(err);
        } finally {
            keys = [];
        }
        return response;
    }

    async function scheduleDelete(key) {
        keys.push({Key: key});
        if (keys.length >= bulkDeleteMaxFiles) return await deleteKeys();
    }

    async function flushDelete() {
        if (keys.length) return await deleteKeys();
    }

    return [scheduleDelete, flushDelete];
}
