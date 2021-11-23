"use strict";

function _instanceof(left, right) { if (right != null && typeof Symbol !== "undefined" && right[Symbol.hasInstance]) { return !!right[Symbol.hasInstance](left); } else { return left instanceof right; } }

function _typeof(obj) { "@babel/helpers - typeof"; if (typeof Symbol === "function" && typeof Symbol.iterator === "symbol") { _typeof = function _typeof(obj) { return typeof obj; }; } else { _typeof = function _typeof(obj) { return obj && typeof Symbol === "function" && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }; } return _typeof(obj); }

function _toConsumableArray(arr) { return _arrayWithoutHoles(arr) || _iterableToArray(arr) || _unsupportedIterableToArray(arr) || _nonIterableSpread(); }

function _nonIterableSpread() { throw new TypeError("Invalid attempt to spread non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }

function _iterableToArray(iter) { if (typeof Symbol !== "undefined" && iter[Symbol.iterator] != null || iter["@@iterator"] != null) return Array.from(iter); }

function _arrayWithoutHoles(arr) { if (Array.isArray(arr)) return _arrayLikeToArray(arr); }

function _slicedToArray(arr, i) { return _arrayWithHoles(arr) || _iterableToArrayLimit(arr, i) || _unsupportedIterableToArray(arr, i) || _nonIterableRest(); }

function _nonIterableRest() { throw new TypeError("Invalid attempt to destructure non-iterable instance.\nIn order to be iterable, non-array objects must have a [Symbol.iterator]() method."); }

function _unsupportedIterableToArray(o, minLen) { if (!o) return; if (typeof o === "string") return _arrayLikeToArray(o, minLen); var n = Object.prototype.toString.call(o).slice(8, -1); if (n === "Object" && o.constructor) n = o.constructor.name; if (n === "Map" || n === "Set") return Array.from(o); if (n === "Arguments" || /^(?:Ui|I)nt(?:8|16|32)(?:Clamped)?Array$/.test(n)) return _arrayLikeToArray(o, minLen); }

function _arrayLikeToArray(arr, len) { if (len == null || len > arr.length) len = arr.length; for (var i = 0, arr2 = new Array(len); i < len; i++) { arr2[i] = arr[i]; } return arr2; }

function _iterableToArrayLimit(arr, i) { var _i = arr == null ? null : typeof Symbol !== "undefined" && arr[Symbol.iterator] || arr["@@iterator"]; if (_i == null) return; var _arr = []; var _n = true; var _d = false; var _s, _e; try { for (_i = _i.call(arr); !(_n = (_s = _i.next()).done); _n = true) { _arr.push(_s.value); if (i && _arr.length === i) break; } } catch (err) { _d = true; _e = err; } finally { try { if (!_n && _i["return"] != null) _i["return"](); } finally { if (_d) throw _e; } } return _arr; }

function _arrayWithHoles(arr) { if (Array.isArray(arr)) return arr; }

function _classCallCheck(instance, Constructor) { if (!_instanceof(instance, Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } }

function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); return Constructor; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function"); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, writable: true, configurable: true } }); if (superClass) _setPrototypeOf(subClass, superClass); }

function _setPrototypeOf(o, p) { _setPrototypeOf = Object.setPrototypeOf || function _setPrototypeOf(o, p) { o.__proto__ = p; return o; }; return _setPrototypeOf(o, p); }

function _createSuper(Derived) { var hasNativeReflectConstruct = _isNativeReflectConstruct(); return function _createSuperInternal() { var Super = _getPrototypeOf(Derived), result; if (hasNativeReflectConstruct) { var NewTarget = _getPrototypeOf(this).constructor; result = Reflect.construct(Super, arguments, NewTarget); } else { result = Super.apply(this, arguments); } return _possibleConstructorReturn(this, result); }; }

function _possibleConstructorReturn(self, call) { if (call && (_typeof(call) === "object" || typeof call === "function")) { return call; } else if (call !== void 0) { throw new TypeError("Derived constructors may only return object or undefined"); } return _assertThisInitialized(self); }

function _assertThisInitialized(self) { if (self === void 0) { throw new ReferenceError("this hasn't been initialised - super() hasn't been called"); } return self; }

function _isNativeReflectConstruct() { if (typeof Reflect === "undefined" || !Reflect.construct) return false; if (Reflect.construct.sham) return false; if (typeof Proxy === "function") return true; try { Boolean.prototype.valueOf.call(Reflect.construct(Boolean, [], function () {})); return true; } catch (e) { return false; } }

function _getPrototypeOf(o) { _getPrototypeOf = Object.setPrototypeOf ? Object.getPrototypeOf : function _getPrototypeOf(o) { return o.__proto__ || Object.getPrototypeOf(o); }; return _getPrototypeOf(o); }

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
// Modified by the Department for International Trade November 2021
angular.module('aws-js-s3-explorer', []);
angular.module('aws-js-s3-explorer').factory('s3', function (Config) {
  function fetchJSON(url) {
    return new Promise(function (resolve, reject) {
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

  var Credentials = /*#__PURE__*/function (_AWS$Credentials) {
    _inherits(Credentials, _AWS$Credentials);

    var _super = _createSuper(Credentials);

    function Credentials() {
      var _this;

      _classCallCheck(this, Credentials);

      _this = _super.call(this);
      _this.expiration = 0;
      return _this;
    }

    _createClass(Credentials, [{
      key: "refresh",
      value: async function refresh(callback) {
        try {
          var response = await fetchJSON(Config.credentialsUrl);
        } catch (err) {
          callback(err);
          return;
        }

        this.accessKeyId = response.AccessKeyId;
        this.secretAccessKey = response.SecretAccessKey;
        this.sessionToken = response.SessionToken;
        this.expiration = Date.parse(response.Expiration);
        callback();
      }
    }, {
      key: "needsRefresh",
      value: function needsRefresh() {
        return this.expiration - 60 < Date.now();
      }
    }]);

    return Credentials;
  }(AWS.Credentials);

  AWS.config.update({
    credentials: new Credentials(),
    region: Config.region
  });
  return new AWS.S3({
    s3ForcePathStyle: true
  });
});
angular.module('aws-js-s3-explorer').run(function ($rootScope) {
  var sizes = ['bytes', 'KB', 'MB', 'GB', 'TB'];

  $rootScope.bytesToSize = function (bytes) {
    if (bytes === 0) return '0 bytes';
    var ii = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10);
    return "".concat(Math.round(bytes / 1024 ** ii, 2), " ").concat(sizes[ii]);
  }; // Convert cars/vw/golf.png to golf.png


  $rootScope.fullpath2filename = function (path) {
    return path.replace(/^.*[\\/]/, '');
  }; // Convert cars/vw/ to vw/


  $rootScope.prefix2folder = function (prefix) {
    var parts = prefix.split('/');
    return "".concat(parts[parts.length - 2], "/");
  };
});
angular.module('aws-js-s3-explorer').controller('ViewController', function (Config, s3, $rootScope, $scope) {
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

  $scope.setCurrentPrefix = function (prefix, $event) {
    $event.stopPropagation();
    currentPrefix = prefix;
    listObjects();
    setBreadcrumbs();
  };

  $scope.numSelected = function () {
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
  };

  $scope.toggleSelected = function (item) {
    item.selected = !item.selected;
  };

  $scope.download = async function (key, $event) {
    $event.stopPropagation();
    var params = {
      Bucket: Config.bucket,
      Key: key,
      Expires: 15,
      ResponseContentDisposition: 'attachment'
    };

    try {
      url = await s3.getSignedUrlPromise('getObject', params);
    } catch (err) {
      $scope.$apply(function () {
        $rootScope.$broadcast('error', {
          params: params,
          err: err
        });
      });
      return;
    }

    window.location.href = url;
  };

  var setBreadcrumbs = function setBreadcrumbs() {
    var prefix = Config.prefix;
    $scope.breadcrumbs = [{
      prefix: prefix,
      label: 'home'
    }];
    var labels = currentPrefix.substring(prefix.length).split('/');

    for (var i = 0; i < labels.length - 1; ++i) {
      prefix += labels[i] + '/';
      $scope.breadcrumbs.push({
        prefix: prefix,
        label: labels[i]
      });
    }
  };

  $scope.$on('reload-object-list', function () {
    listObjects();
  });

  $scope.listObjects = function () {
    $scope.$broadcast('spinner::start::refresh');
    listObjects();
  };

  var listObjects = async function listObjects() {
    // This is an async function, so copy variables that could change during to avoid
    // future gotchas
    var prefix = currentPrefix;
    var bucket = Config.bucket;
    var params = {
      Bucket: bucket,
      Prefix: prefix,
      Delimiter: '/'
    };

    try {
      response = await s3.listObjectsV2(params).promise();
      $scope.$apply(function () {
        $scope.bigdata = prefix == originalPrefix ? {
          Prefix: originalPrefix + Config.bigdataPrefix
        } : null;
        $scope.prefixes = response.CommonPrefixes.filter(function (prefix) {
          return prefix.Prefix != originalPrefix + Config.bigdataPrefix;
        });
        $scope.objects = response.Contents.filter(function (object) {
          return object.Key != prefix;
        }).map(function (object) {
          object.isCsv = object.Key.substr(object.Key.length - 3, object.Key.length) === 'csv';
          return object;
        });
        $scope.initialising = false;
        $scope.inBigdata = startsWith(currentPrefix, originalPrefix + Config.bigdataPrefix);
      });
    } catch (err) {
      $scope.$apply(function () {
        $rootScope.$broadcast('error', {
          params: params,
          err: err
        });
      });
    }
  };

  $scope.openAddFolderModal = function () {
    $rootScope.$broadcast('modal::open::add-folder', {
      bucket: Config.bucket,
      currentPrefix: currentPrefix
    });
  };

  $scope.filesSelected = function (files) {
    $rootScope.$broadcast('modal::open::upload', {
      bucket: Config.bucket,
      originalPrefix: originalPrefix,
      currentPrefix: currentPrefix,
      files: files
    });
  };

  $scope.$on('dropzone::files', function (e, files) {
    $rootScope.$broadcast('modal::open::upload', {
      bucket: Config.bucket,
      originalPrefix: originalPrefix,
      currentPrefix: currentPrefix,
      files: files
    });
  });

  $scope.openFileBrowser = function () {
    $scope.$broadcast('open-file-browser');
  };

  $scope.openTrashModal = function () {
    var prefixes = $scope.prefixes.filter(function (prefix) {
      return prefix.selected;
    });
    var objects = $scope.objects.filter(function (object) {
      return object.selected;
    });
    $rootScope.$broadcast('modal::open::trash', {
      bucket: Config.bucket,
      prefixes: prefixes,
      objects: objects
    });
  };

  listObjects();
  setBreadcrumbs();
});
angular.module('aws-js-s3-explorer').controller('AddFolderController', function (s3, $scope, $rootScope) {
  $scope.$on('modal::open::add-folder', function (e, args) {
    $scope.model = {
      bucket: args.bucket,
      currentPrefix: args.currentPrefix,
      newFolder: ''
    };
  });

  $scope.addFolder = async function () {
    var withoutLeadTrailSlash = $scope.model.newFolder.replace(/^\/+/g, '').replace(/\/+$/g, '');
    var folder = $scope.model.currentPrefix + withoutLeadTrailSlash + '/';
    var params = {
      Bucket: $scope.model.bucket,
      Key: folder
    };
    var canCreate = false; // Slightly awkward since a 404 is converted to an exception

    try {
      await s3.headObject(params).promise();
    } catch (err) {
      canCreate = err.code === 'NotFound';

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
angular.module('aws-js-s3-explorer').controller('UploadController', function (s3, $scope, $rootScope) {
  function queue(concurrency) {
    var running = 0;
    var tasks = [];
    return async function run(task) {
      tasks.push(task);
      if (running >= concurrency) return;
      ++running;

      while (tasks.length) {
        try {
          await tasks.shift()();
        } catch (err) {
          console.error(err);
        }
      }

      --running;
    };
  }

  $scope.$on('modal::open::upload', function (e, args) {
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
    var maxConnections = 4;
    var concurrentFiles = Math.min(maxConnections, args.files.length);
    var connectionsPerFile = Math.floor(maxConnections / concurrentFiles);
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
  $scope.$on('modal::close::upload', function () {
    $scope.model.aborted = true;
    $scope.model.uploads.forEach(function (upload) {
      upload.abort();
    });
  });
  $scope.$on('modal::close-end::upload', function (e, args) {
    $scope.model.uploads = [];
    $scope.model.files = [];
  });

  $scope.uploadFiles = function () {
    $scope.model.uploading = true;
    $scope.model.files.forEach(function (file) {
      // If things are horribly slow and the user is quick, we could have opened a "new"
      // model from the point of view of the user, but still in the process of the abort
      // of the old, and so we ensure to only modify the original model
      var model = $scope.model;
      var params = {
        Bucket: model.bucket,
        Key: model.currentPrefix + file.relativePath,
        ContentType: file.type,
        Body: file
      };

      var onProgress = function onProgress(evt) {
        var pc = evt.total ? evt.loaded * 100.0 / evt.total : 0;
        var pct = Math.round(pc);
        $scope.$apply(function () {
          file.progress = pct;
        });
      };

      model.queue(async function () {
        try {
          if (!model.aborted) {
            var upload = s3.upload(params, {
              queueSize: model.connectionsPerFile
            });
            model.uploads.push(upload);
            await upload.on('httpUploadProgress', onProgress).promise();
          }
        } catch (err) {
          if (!model.aborted) {
            console.error(err);
            $scope.$apply(function () {
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
angular.module('aws-js-s3-explorer').controller('ErrorController', function ($scope) {
  // Not using Object.entries for IE11 support
  function objEntries(obj) {
    var ownProps = Object.keys(obj);
    var i = ownProps.length;
    var resArray = new Array(i);

    while (i--) {
      resArray[i] = [ownProps[i], obj[ownProps[i]]];
    }

    return resArray;
  }

  $scope.$on('error', function (e, args) {
    var params = args.params,
        err = args.err;
    var message = err && 'message' in err ? err.message : '';
    var code = err && 'code' in err ? err.code : '';
    var errors = objEntries(err || {}).map(function (_ref) {
      var _ref2 = _slicedToArray(_ref, 2),
          key = _ref2[0],
          value = _ref2[1];

      return {
        key: key,
        value: value
      };
    });
    $scope.error = {
      params: params,
      message: message,
      code: code,
      errors: errors
    };
    $scope.$broadcast('modal::open::error');
  });
  $scope.error = {
    errors: [],
    message: ''
  };
});
angular.module('aws-js-s3-explorer').controller('TrashController', function (s3, $scope, $rootScope) {
  $scope.$on('modal::open::trash', function (e, args) {
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
  $scope.$on('modal::close::trash', function (e, args) {
    $scope.model.aborted = true;
  });
  $scope.$on('modal::close-end::trash', function (e, args) {
    $scope.model.prefixes = [];
    $scope.model.objects = [];
  });

  $scope.deleteFiles = async function () {
    var model = $scope.model;
    model.trashing = true;

    var _Deleter = Deleter(s3, model.bucket),
        _Deleter2 = _slicedToArray(_Deleter, 2),
        scheduleDelete = _Deleter2[0],
        flushDelete = _Deleter2[1]; // Slight hack to ensure that we are no longer in a digest, to make
    // each iteration of the below loop able to assume it's not in a digest


    await new Promise(function (resolve) {
      return window.setTimeout(resolve);
    });

    var setObjectMessage = function setObjectMessage(obj, messageKey, messageText) {
      if (!model.aborted) {
        $scope.$apply(function () {
          obj[messageKey] = messageText;
        });
      }
    }; // Delete prefixes: fetch all keys under them, deleting as we go to avoid storing in memory


    for (var i = 0; i < model.prefixes.length && !model.aborted; ++i) {
      var prefix = model.prefixes[i];
      setObjectMessage(prefix, 'deleteStarted', true); // Attempt to list objects under the prefix. If the list objects
      // call fails, update the model and try the next prefix.

      var continuationToken = null;
      var isTruncated = true;

      while (isTruncated && !model.aborted) {
        var _response = void 0;

        try {
          _response = await s3.listObjectsV2({
            Bucket: model.bucket,
            Prefix: prefix.Prefix,
            ContinuationToken: continuationToken
          }).promise();
          continuationToken = _response.NextContinuationToken;
          isTruncated = _response.IsTruncated;
        } catch (err) {
          console.error(err);
          setObjectMessage(prefix, 'deleteError', err.code || err.message || err);
          continue;
        } // Loop through the objects within the prefix and bulk delete them


        for (var j = 0; j < _response.Contents.length && !model.aborted; ++j) {
          try {
            await scheduleDelete(_response.Contents[j].Key);
          } catch (err) {
            setObjectMessage(prefix, 'deleteError', err.code || err.message || err);
            break;
          }
        }
      }

      try {
        await flushDelete();
      } catch (err) {
        setObjectMessage(prefix, 'deleteError', err.code || err.message || err);
        continue;
      }

      setObjectMessage(prefix, 'deleteFinished', true);
    } // Delete objects
    // Find an object by key in the model's list of objects


    var updateObject = function updateObject(key, messageKey, message) {
      var objs = model.objects.filter(function (o) {
        return o.Key === key;
      });

      if (objs.length > 0) {
        setObjectMessage(objs[0], messageKey, message);
      }
    }; // Process the bulk delete response from s3.
    // Sets the `deleteFinished` or `deleteError` attribute accordingly


    var processResponse = function processResponse(response) {
      if (typeof response === 'undefined') return; // Update objects that were successfully deleted

      for (var _i2 = 0; _i2 < response.Deleted.length; _i2++) {
        updateObject(response.Deleted[_i2].Key, 'deleteFinished', true);
      } // Update objects that had errors


      for (var _i3 = 0; _i3 < response.Errors.length; _i3++) {
        updateObject(response.Errors[_i3].Key, 'deleteError', response.Errors[_i3].Code || response.Errors[_i3].Message);
      }
    };

    for (var _i4 = 0; _i4 < model.objects.length && !model.aborted; ++_i4) {
      processResponse(await scheduleDelete(model.objects[_i4].Key));
    }

    processResponse(await flushDelete());
    setObjectMessage($scope.model, 'finished', true);
    $rootScope.$broadcast('reload-object-list');
  };
});
angular.module('aws-js-s3-explorer').directive('modal', function () {
  var backdrop = document.createElement('div');
  backdrop.className = 'modal-backdrop';
  document.body.appendChild(backdrop); // Without CSS, we don't get transitionend events

  var cssEnabled = window.getComputedStyle(backdrop).getPropertyValue('visibility') == 'hidden';
  return {
    link: function link(scope, element, attrs) {
      var name = attrs.modal;
      element[0].addEventListener('click', function (event) {
        event.stopPropagation(); // Don't close if clicking anywhere inside the modal, e.g. on a button

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
      } // A bit brittle WRT the transitions, but KISS


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
angular.module('aws-js-s3-explorer').directive('onFileChange', function ($timeout) {
  return {
    scope: {
      onFileChange: '&'
    },
    link: function link(scope, element, attrs) {
      element[0].addEventListener('change', function (event) {
        // Ensure we have an Array
        var files = [];

        for (var i = 0; i < event.target.files.length; ++i) {
          var file = event.target.files[i]; // Monkey patch to make the files similar to how they are from drag and drop

          file.relativePath = file.name;
          files.push(file);
        } // In IE11, we seem to be in a digest, but in Chrome/FF, we're not. So we trigger
        // the callback in a $timeout to safely jump out of a digest if we're in one, and
        // into another. The change happens on a click, so short delay here is fine


        $timeout(function () {
          scope.onFileChange({
            files: files
          });
        });
      });
    }
  };
});
angular.module('aws-js-s3-explorer').directive('triggerClickOn', function () {
  return {
    link: function link(scope, element, attrs) {
      scope.$on(attrs.triggerClickOn, function () {
        element[0].click();
      });
    }
  };
});
angular.module('aws-js-s3-explorer').directive('focusOn', function () {
  return {
    link: function link(scope, element, attrs) {
      scope.$on(attrs.focusOn, function () {
        element[0].focus();
      });
    }
  };
});
angular.module('aws-js-s3-explorer').directive('dropzone', function () {
  async function entries(directoryReader) {
    var entries = [];

    while (true) {
      var latestEntries = await new Promise(function (resolve, reject) {
        directoryReader.readEntries(resolve, reject);
      });
      if (latestEntries.length == 0) break;
      entries = entries.concat(latestEntries);
    }

    return entries;
  }

  async function file(fileEntry) {
    var file = await new Promise(function (resolve, reject) {
      fileEntry.file(resolve, reject);
    }); // We monkey-patch the file to include its FileSystemEntry fullPath,
    // which is a path relative to the root of the pseudo-filesystem of
    // a dropped folder

    file.relativePath = fileEntry.fullPath.substring(1); // Remove leading slash

    return file;
  }

  async function getFiles(dataTransferItemList) {
    var files = []; // DataTransferItemList does not support map

    fileAndDirectoryEntryQueue = [];

    for (var i = 0; i < dataTransferItemList.length; ++i) {
      // At the time of writing no browser supports `getAsEntry`
      fileAndDirectoryEntryQueue.push(dataTransferItemList[i].webkitGetAsEntry());
    }

    while (fileAndDirectoryEntryQueue.length > 0) {
      var entry = fileAndDirectoryEntryQueue.shift();

      if (entry.isFile) {
        files.push(await file(entry));
      } else if (entry.isDirectory) {
        var _fileAndDirectoryEntr;

        (_fileAndDirectoryEntr = fileAndDirectoryEntryQueue).push.apply(_fileAndDirectoryEntr, _toConsumableArray(await entries(entry.createReader())));
      }
    }

    return files;
  }

  return {
    link: function link(scope, element, attrs) {
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
        var files = await getFiles(event.dataTransfer.items);
        scope.$apply(function () {
          scope.$broadcast('dropzone::files', files);
        });
      }
    }
  };
});
angular.module('aws-js-s3-explorer').directive('spinner', function () {
  return {
    link: function link(scope, element, attrs) {
      var name = attrs.spinner;
      scope.$on('spinner::start::' + name, function () {
        element[0].classList.add('spin');
      });
      element[0].addEventListener('animationend', function () {
        element[0].classList.remove('spin');
      });
    }
  };
});

function Deleter(s3, bucket) {
  var bulkDeleteMaxFiles = 1000;
  var keys = [];

  async function deleteKeys() {
    var response;

    try {
      response = await s3.deleteObjects({
        Bucket: bucket,
        Delete: {
          Objects: keys
        }
      }).promise();
    } catch (err) {
      console.error(err);
      throw err;
    } finally {
      keys = [];
    }

    return response;
  }

  async function scheduleDelete(key) {
    keys.push({
      Key: key
    });
    if (keys.length >= bulkDeleteMaxFiles) return await deleteKeys();
  }

  async function flushDelete() {
    if (keys.length) return await deleteKeys();
  }

  return [scheduleDelete, flushDelete];
}