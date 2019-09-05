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

angular.module('aws-js-s3-explorer').run((Config, $rootScope) => {
    AWS.config.update(Config.credentials);
    AWS.config.update({region: Config.region});

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

angular.module('aws-js-s3-explorer').controller('ViewController', ($scope, Config, $rootScope) => {
    var originalPrefix = Config.prefix;
    var currentPrefix = Config.prefix;

    $scope.breadcrumbs = [];
    $scope.bigdata = null;
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
        const s3 = new AWS.S3();
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
        const s3 = new AWS.S3(AWS.config);
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
                });
                $scope.initialising = false;
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

angular.module('aws-js-s3-explorer').controller('AddFolderController', ($scope, $rootScope) => {
    $scope.$on('modal::open::add-folder', (e, args) => {
        $scope.model = {
            bucket: args.bucket,
            currentPrefix: args.currentPrefix,
            newFolder: ''
        };
    });

    $scope.addFolder = async () => {
        const s3 = new AWS.S3(AWS.config);
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

angular.module('aws-js-s3-explorer').controller('UploadController', ($scope, $rootScope) => {
    $scope.$on('modal::open::upload', (e, args) => {
        var folder = args.currentPrefix.substring(args.originalPrefix.length);
        $scope.model = {
            bucket: args.bucket,
            folder: folder == '' ? 'home/' : $scope.prefix2folder(folder),
            currentPrefix: args.currentPrefix,
            files: args.files,
            remaining: args.files.length,
            uploading: false,
            aborted: false,
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
        const s3 = new AWS.S3(AWS.config);

        $scope.model.files.forEach(async (file) => {
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

            // Slight hack to yield the event loop to not start a long list of uploads all at once
            await new Promise((resolve) => window.setTimeout(resolve));

            try {
                if (!model.aborted) {
                    let upload = s3.upload(params);
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
    };
});

angular.module('aws-js-s3-explorer').controller('ErrorController', ($scope) => {
    $scope.$on('error', (e, args) => {
        const { params, err } = args;

        const message = err && 'message' in err ? err.message : '';
        const code = err && 'code' in err ? err.code : '';
        const errors = Object.entries(err || {}).map(([key, value]) => ({ key, value }));

        $scope.error = { params, message, code, errors };
        $scope.$broadcast('modal::open::error');
    });

    $scope.error = {
        errors: [], message: '',
    };
});

angular.module('aws-js-s3-explorer').controller('TrashController', ($scope, $rootScope) => {
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
        var model = $scope.model;
        model.trashing = true;

        const s3 = new AWS.S3(AWS.config);

        // Slight hack to ensure that we are no longer in a digest, to make
        // each iteration of the below loop able to assume it's not in a digest
        await new Promise((resolve) => window.setTimeout(resolve));

        // Delete prefixes: fetch all keys under them, deleting as we go to avoid storing in memory
        for (let i = 0; i < model.prefixes.length && !model.aborted; ++i) {
            let prefix = model.prefixes[i];
            try {
                $scope.$apply(() => {
                    prefix.deleteStarted = true;
                });
                let isTruncated = true;
                let continuationToken = null;
                while (isTruncated) {
                    response = await s3.listObjectsV2({
                        Bucket: model.bucket,
                        Prefix: prefix.Prefix,
                        ContinuationToken: continuationToken
                    }).promise()
                    isTruncated = response.IsTruncated;
                    continuationToken = response.NextContinuationToken;
                    for (let j = 0; j < response.Contents.length && !model.aborted; ++j) {
                        await s3.deleteObject({ Bucket: model.bucket, Key: response.Contents[j].Key }).promise();
                    }
                }
                if (!model.aborted) {
                    $scope.$apply(() => {
                        prefix.deleteFinished = true;
                    });
                }
            } catch(err) {
                console.error(err);
                if (!model.aborted) {
                    $scope.$apply(() => {
                        prefix.deleteError = err.code || err.message || err;
                    });
                }
            }
        }

        // Delete objects
        for (let i = 0; i < model.objects.length && !model.aborted; ++i) {
            let object = model.objects[i];
            try {
                await s3.deleteObject({ Bucket: model.bucket, Key: object.Key }).promise();
                if (!model.aborted) {
                    $scope.$apply(() => {
                        object.deleteFinished = true;
                    });
                }
            } catch(err) {
                console.error(err);
                if (!model.aborted) {
                    $scope.$apply(() => {
                        object.deleteError = err.code || err.message || err;
                    });
                }
            }
        }

        if (!model.aborted) {
            $scope.$apply(() => {
                $scope.model.finished = true;
            });
        }
        $rootScope.$broadcast('reload-object-list');
    };
});

angular.module('aws-js-s3-explorer').directive('modal', () => {
    var backdrop = document.createElement('div');
    backdrop.className = 'modal-backdrop';
    document.body.appendChild(backdrop);

    return {
        link: function(scope, element, attrs) {
            var name = attrs.modal;
            element[0].addEventListener('click', close);
            element[0].firstElementChild.addEventListener('click', (event) => {
                event.stopPropagation();
            });
            function open() {
                backdrop.classList.remove('modal-backdrop-out');
                backdrop.classList.add('modal-backdrop-in');
                element[0].classList.remove('modal-out');
                element[0].classList.add('modal-in');
                element[0].removeAttribute('aria-hidden');
                element[0].addEventListener('transitionend', broadcastOpenEnd);
                document.addEventListener('keydown', closeIfEscape);
            }
            function close() {
                backdrop.classList.remove('modal-backdrop-in');
                backdrop.classList.add('modal-backdrop-out');
                element[0].classList.remove('modal-in');
                element[0].classList.add('modal-out');
                element[0].setAttribute('aria-hidden', 'true');
                document.removeEventListener('keydown', closeIfEscape);
                element[0].removeEventListener('transitionend', broadcastOpenEnd);
            }
            function closeIfEscape(event) {
                if (event.key === 'Escape') {
                    close();
                }
            }
            function broadcastOpenEnd(e) {
                // A bit brittle WRT the transitions, but KISS
                if (e.propertyName == 'top') {
                    scope.$broadcast('modal::open-end::' + name)
                }
            }
            scope.$on('modal::open::' + name, open);
            scope.$on('modal::close::' + name, close);
        }
    };
});

angular.module('aws-js-s3-explorer').directive('onFileChange', () => {
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
                scope.$apply(() => {
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
