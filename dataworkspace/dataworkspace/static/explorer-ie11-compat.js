function _typeof(obj) { "@babel/helpers - typeof"; return _typeof = "function" == typeof Symbol && "symbol" == typeof Symbol.iterator ? function (obj) { return typeof obj; } : function (obj) { return obj && "function" == typeof Symbol && obj.constructor === Symbol && obj !== Symbol.prototype ? "symbol" : typeof obj; }, _typeof(obj); }

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

function _regeneratorRuntime() { "use strict"; /*! regenerator-runtime -- Copyright (c) 2014-present, Facebook, Inc. -- license (MIT): https://github.com/facebook/regenerator/blob/main/LICENSE */ _regeneratorRuntime = function _regeneratorRuntime() { return exports; }; var exports = {}, Op = Object.prototype, hasOwn = Op.hasOwnProperty, $Symbol = "function" == typeof Symbol ? Symbol : {}, iteratorSymbol = $Symbol.iterator || "@@iterator", asyncIteratorSymbol = $Symbol.asyncIterator || "@@asyncIterator", toStringTagSymbol = $Symbol.toStringTag || "@@toStringTag"; function define(obj, key, value) { return Object.defineProperty(obj, key, { value: value, enumerable: !0, configurable: !0, writable: !0 }), obj[key]; } try { define({}, ""); } catch (err) { define = function define(obj, key, value) { return obj[key] = value; }; } function wrap(innerFn, outerFn, self, tryLocsList) { var protoGenerator = outerFn && outerFn.prototype instanceof Generator ? outerFn : Generator, generator = Object.create(protoGenerator.prototype), context = new Context(tryLocsList || []); return generator._invoke = function (innerFn, self, context) { var state = "suspendedStart"; return function (method, arg) { if ("executing" === state) throw new Error("Generator is already running"); if ("completed" === state) { if ("throw" === method) throw arg; return doneResult(); } for (context.method = method, context.arg = arg;;) { var delegate = context.delegate; if (delegate) { var delegateResult = maybeInvokeDelegate(delegate, context); if (delegateResult) { if (delegateResult === ContinueSentinel) continue; return delegateResult; } } if ("next" === context.method) context.sent = context._sent = context.arg;else if ("throw" === context.method) { if ("suspendedStart" === state) throw state = "completed", context.arg; context.dispatchException(context.arg); } else "return" === context.method && context.abrupt("return", context.arg); state = "executing"; var record = tryCatch(innerFn, self, context); if ("normal" === record.type) { if (state = context.done ? "completed" : "suspendedYield", record.arg === ContinueSentinel) continue; return { value: record.arg, done: context.done }; } "throw" === record.type && (state = "completed", context.method = "throw", context.arg = record.arg); } }; }(innerFn, self, context), generator; } function tryCatch(fn, obj, arg) { try { return { type: "normal", arg: fn.call(obj, arg) }; } catch (err) { return { type: "throw", arg: err }; } } exports.wrap = wrap; var ContinueSentinel = {}; function Generator() {} function GeneratorFunction() {} function GeneratorFunctionPrototype() {} var IteratorPrototype = {}; define(IteratorPrototype, iteratorSymbol, function () { return this; }); var getProto = Object.getPrototypeOf, NativeIteratorPrototype = getProto && getProto(getProto(values([]))); NativeIteratorPrototype && NativeIteratorPrototype !== Op && hasOwn.call(NativeIteratorPrototype, iteratorSymbol) && (IteratorPrototype = NativeIteratorPrototype); var Gp = GeneratorFunctionPrototype.prototype = Generator.prototype = Object.create(IteratorPrototype); function defineIteratorMethods(prototype) { ["next", "throw", "return"].forEach(function (method) { define(prototype, method, function (arg) { return this._invoke(method, arg); }); }); } function AsyncIterator(generator, PromiseImpl) { function invoke(method, arg, resolve, reject) { var record = tryCatch(generator[method], generator, arg); if ("throw" !== record.type) { var result = record.arg, value = result.value; return value && "object" == _typeof(value) && hasOwn.call(value, "__await") ? PromiseImpl.resolve(value.__await).then(function (value) { invoke("next", value, resolve, reject); }, function (err) { invoke("throw", err, resolve, reject); }) : PromiseImpl.resolve(value).then(function (unwrapped) { result.value = unwrapped, resolve(result); }, function (error) { return invoke("throw", error, resolve, reject); }); } reject(record.arg); } var previousPromise; this._invoke = function (method, arg) { function callInvokeWithMethodAndArg() { return new PromiseImpl(function (resolve, reject) { invoke(method, arg, resolve, reject); }); } return previousPromise = previousPromise ? previousPromise.then(callInvokeWithMethodAndArg, callInvokeWithMethodAndArg) : callInvokeWithMethodAndArg(); }; } function maybeInvokeDelegate(delegate, context) { var method = delegate.iterator[context.method]; if (undefined === method) { if (context.delegate = null, "throw" === context.method) { if (delegate.iterator.return && (context.method = "return", context.arg = undefined, maybeInvokeDelegate(delegate, context), "throw" === context.method)) return ContinueSentinel; context.method = "throw", context.arg = new TypeError("The iterator does not provide a 'throw' method"); } return ContinueSentinel; } var record = tryCatch(method, delegate.iterator, context.arg); if ("throw" === record.type) return context.method = "throw", context.arg = record.arg, context.delegate = null, ContinueSentinel; var info = record.arg; return info ? info.done ? (context[delegate.resultName] = info.value, context.next = delegate.nextLoc, "return" !== context.method && (context.method = "next", context.arg = undefined), context.delegate = null, ContinueSentinel) : info : (context.method = "throw", context.arg = new TypeError("iterator result is not an object"), context.delegate = null, ContinueSentinel); } function pushTryEntry(locs) { var entry = { tryLoc: locs[0] }; 1 in locs && (entry.catchLoc = locs[1]), 2 in locs && (entry.finallyLoc = locs[2], entry.afterLoc = locs[3]), this.tryEntries.push(entry); } function resetTryEntry(entry) { var record = entry.completion || {}; record.type = "normal", delete record.arg, entry.completion = record; } function Context(tryLocsList) { this.tryEntries = [{ tryLoc: "root" }], tryLocsList.forEach(pushTryEntry, this), this.reset(!0); } function values(iterable) { if (iterable) { var iteratorMethod = iterable[iteratorSymbol]; if (iteratorMethod) return iteratorMethod.call(iterable); if ("function" == typeof iterable.next) return iterable; if (!isNaN(iterable.length)) { var i = -1, next = function next() { for (; ++i < iterable.length;) { if (hasOwn.call(iterable, i)) return next.value = iterable[i], next.done = !1, next; } return next.value = undefined, next.done = !0, next; }; return next.next = next; } } return { next: doneResult }; } function doneResult() { return { value: undefined, done: !0 }; } return GeneratorFunction.prototype = GeneratorFunctionPrototype, define(Gp, "constructor", GeneratorFunctionPrototype), define(GeneratorFunctionPrototype, "constructor", GeneratorFunction), GeneratorFunction.displayName = define(GeneratorFunctionPrototype, toStringTagSymbol, "GeneratorFunction"), exports.isGeneratorFunction = function (genFun) { var ctor = "function" == typeof genFun && genFun.constructor; return !!ctor && (ctor === GeneratorFunction || "GeneratorFunction" === (ctor.displayName || ctor.name)); }, exports.mark = function (genFun) { return Object.setPrototypeOf ? Object.setPrototypeOf(genFun, GeneratorFunctionPrototype) : (genFun.__proto__ = GeneratorFunctionPrototype, define(genFun, toStringTagSymbol, "GeneratorFunction")), genFun.prototype = Object.create(Gp), genFun; }, exports.awrap = function (arg) { return { __await: arg }; }, defineIteratorMethods(AsyncIterator.prototype), define(AsyncIterator.prototype, asyncIteratorSymbol, function () { return this; }), exports.AsyncIterator = AsyncIterator, exports.async = function (innerFn, outerFn, self, tryLocsList, PromiseImpl) { void 0 === PromiseImpl && (PromiseImpl = Promise); var iter = new AsyncIterator(wrap(innerFn, outerFn, self, tryLocsList), PromiseImpl); return exports.isGeneratorFunction(outerFn) ? iter : iter.next().then(function (result) { return result.done ? result.value : iter.next(); }); }, defineIteratorMethods(Gp), define(Gp, toStringTagSymbol, "Generator"), define(Gp, iteratorSymbol, function () { return this; }), define(Gp, "toString", function () { return "[object Generator]"; }), exports.keys = function (object) { var keys = []; for (var key in object) { keys.push(key); } return keys.reverse(), function next() { for (; keys.length;) { var key = keys.pop(); if (key in object) return next.value = key, next.done = !1, next; } return next.done = !0, next; }; }, exports.values = values, Context.prototype = { constructor: Context, reset: function reset(skipTempReset) { if (this.prev = 0, this.next = 0, this.sent = this._sent = undefined, this.done = !1, this.delegate = null, this.method = "next", this.arg = undefined, this.tryEntries.forEach(resetTryEntry), !skipTempReset) for (var name in this) { "t" === name.charAt(0) && hasOwn.call(this, name) && !isNaN(+name.slice(1)) && (this[name] = undefined); } }, stop: function stop() { this.done = !0; var rootRecord = this.tryEntries[0].completion; if ("throw" === rootRecord.type) throw rootRecord.arg; return this.rval; }, dispatchException: function dispatchException(exception) { if (this.done) throw exception; var context = this; function handle(loc, caught) { return record.type = "throw", record.arg = exception, context.next = loc, caught && (context.method = "next", context.arg = undefined), !!caught; } for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i], record = entry.completion; if ("root" === entry.tryLoc) return handle("end"); if (entry.tryLoc <= this.prev) { var hasCatch = hasOwn.call(entry, "catchLoc"), hasFinally = hasOwn.call(entry, "finallyLoc"); if (hasCatch && hasFinally) { if (this.prev < entry.catchLoc) return handle(entry.catchLoc, !0); if (this.prev < entry.finallyLoc) return handle(entry.finallyLoc); } else if (hasCatch) { if (this.prev < entry.catchLoc) return handle(entry.catchLoc, !0); } else { if (!hasFinally) throw new Error("try statement without catch or finally"); if (this.prev < entry.finallyLoc) return handle(entry.finallyLoc); } } } }, abrupt: function abrupt(type, arg) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.tryLoc <= this.prev && hasOwn.call(entry, "finallyLoc") && this.prev < entry.finallyLoc) { var finallyEntry = entry; break; } } finallyEntry && ("break" === type || "continue" === type) && finallyEntry.tryLoc <= arg && arg <= finallyEntry.finallyLoc && (finallyEntry = null); var record = finallyEntry ? finallyEntry.completion : {}; return record.type = type, record.arg = arg, finallyEntry ? (this.method = "next", this.next = finallyEntry.finallyLoc, ContinueSentinel) : this.complete(record); }, complete: function complete(record, afterLoc) { if ("throw" === record.type) throw record.arg; return "break" === record.type || "continue" === record.type ? this.next = record.arg : "return" === record.type ? (this.rval = this.arg = record.arg, this.method = "return", this.next = "end") : "normal" === record.type && afterLoc && (this.next = afterLoc), ContinueSentinel; }, finish: function finish(finallyLoc) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.finallyLoc === finallyLoc) return this.complete(entry.completion, entry.afterLoc), resetTryEntry(entry), ContinueSentinel; } }, catch: function _catch(tryLoc) { for (var i = this.tryEntries.length - 1; i >= 0; --i) { var entry = this.tryEntries[i]; if (entry.tryLoc === tryLoc) { var record = entry.completion; if ("throw" === record.type) { var thrown = record.arg; resetTryEntry(entry); } return thrown; } } throw new Error("illegal catch attempt"); }, delegateYield: function delegateYield(iterable, resultName, nextLoc) { return this.delegate = { iterator: values(iterable), resultName: resultName, nextLoc: nextLoc }, "next" === this.method && (this.arg = undefined), ContinueSentinel; } }, exports; }

function asyncGeneratorStep(gen, resolve, reject, _next, _throw, key, arg) { try { var info = gen[key](arg); var value = info.value; } catch (error) { reject(error); return; } if (info.done) { resolve(value); } else { Promise.resolve(value).then(_next, _throw); } }

function _asyncToGenerator(fn) { return function () { var self = this, args = arguments; return new Promise(function (resolve, reject) { var gen = fn.apply(self, args); function _next(value) { asyncGeneratorStep(gen, resolve, reject, _next, _throw, "next", value); } function _throw(err) { asyncGeneratorStep(gen, resolve, reject, _next, _throw, "throw", err); } _next(undefined); }); }; }

function _classCallCheck(instance, Constructor) { if (!(instance instanceof Constructor)) { throw new TypeError("Cannot call a class as a function"); } }

function _defineProperties(target, props) { for (var i = 0; i < props.length; i++) { var descriptor = props[i]; descriptor.enumerable = descriptor.enumerable || false; descriptor.configurable = true; if ("value" in descriptor) descriptor.writable = true; Object.defineProperty(target, descriptor.key, descriptor); } }

function _createClass(Constructor, protoProps, staticProps) { if (protoProps) _defineProperties(Constructor.prototype, protoProps); if (staticProps) _defineProperties(Constructor, staticProps); Object.defineProperty(Constructor, "prototype", { writable: false }); return Constructor; }

function _inherits(subClass, superClass) { if (typeof superClass !== "function" && superClass !== null) { throw new TypeError("Super expression must either be null or a function"); } subClass.prototype = Object.create(superClass && superClass.prototype, { constructor: { value: subClass, writable: true, configurable: true } }); Object.defineProperty(subClass, "prototype", { writable: false }); if (superClass) _setPrototypeOf(subClass, superClass); }

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
// Modified by the Department for International Trade
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
    "use strict";

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
      value: function () {
        var _refresh = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee(callback) {
          var response;
          return _regeneratorRuntime().wrap(function _callee$(_context) {
            while (1) {
              switch (_context.prev = _context.next) {
                case 0:
                  _context.prev = 0;
                  _context.next = 3;
                  return fetchJSON(Config.credentialsUrl);

                case 3:
                  response = _context.sent;
                  _context.next = 10;
                  break;

                case 6:
                  _context.prev = 6;
                  _context.t0 = _context["catch"](0);
                  callback(_context.t0);
                  return _context.abrupt("return");

                case 10:
                  this.accessKeyId = response.AccessKeyId;
                  this.secretAccessKey = response.SecretAccessKey;
                  this.sessionToken = response.SessionToken;
                  this.expiration = Date.parse(response.Expiration);
                  callback();

                case 15:
                case "end":
                  return _context.stop();
              }
            }
          }, _callee, this, [[0, 6]]);
        }));

        function refresh(_x) {
          return _refresh.apply(this, arguments);
        }

        return refresh;
      }()
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

  if (Config.endpointUrl) {
    AWS.config.update({
      endpoint: Config.endpointUrl
    });
  }

  return new AWS.S3({
    s3ForcePathStyle: true
  });
});
angular.module('aws-js-s3-explorer').run(function ($rootScope) {
  var sizes = ['bytes', 'KB', 'MB', 'GB', 'TB'];

  $rootScope.bytesToSize = function (bytes) {
    if (bytes === 0) return '0 bytes';
    var ii = parseInt(Math.floor(Math.log(bytes) / Math.log(1024)), 10);
    return "".concat(Math.round(bytes / Math.pow(1024, ii), 2), " ").concat(sizes[ii]);
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

  $scope.download = /*#__PURE__*/function () {
    var _ref = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee2(key, $event) {
      var params;
      return _regeneratorRuntime().wrap(function _callee2$(_context2) {
        while (1) {
          switch (_context2.prev = _context2.next) {
            case 0:
              $event.stopPropagation();
              params = {
                Bucket: Config.bucket,
                Key: key,
                Expires: 15,
                ResponseContentDisposition: 'attachment'
              };
              _context2.prev = 2;
              _context2.next = 5;
              return s3.getSignedUrlPromise('getObject', params);

            case 5:
              url = _context2.sent;
              _context2.next = 12;
              break;

            case 8:
              _context2.prev = 8;
              _context2.t0 = _context2["catch"](2);
              $scope.$apply(function () {
                $rootScope.$broadcast('error', {
                  params: params,
                  err: _context2.t0
                });
              });
              return _context2.abrupt("return");

            case 12:
              window.location.href = url;

            case 13:
            case "end":
              return _context2.stop();
          }
        }
      }, _callee2, null, [[2, 8]]);
    }));

    return function (_x2, _x3) {
      return _ref.apply(this, arguments);
    };
  }();

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

  var listObjects = /*#__PURE__*/function () {
    var _ref2 = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee3() {
      var prefix, bucket, params;
      return _regeneratorRuntime().wrap(function _callee3$(_context3) {
        while (1) {
          switch (_context3.prev = _context3.next) {
            case 0:
              // This is an async function, so copy variables that could change during to avoid
              // future gotchas
              prefix = currentPrefix;
              bucket = Config.bucket;
              params = {
                Bucket: bucket,
                Prefix: prefix,
                Delimiter: '/'
              };
              _context3.prev = 3;
              _context3.next = 6;
              return s3.listObjectsV2(params).promise();

            case 6:
              response = _context3.sent;
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
              _context3.next = 13;
              break;

            case 10:
              _context3.prev = 10;
              _context3.t0 = _context3["catch"](3);
              $scope.$apply(function () {
                $rootScope.$broadcast('error', {
                  params: params,
                  err: _context3.t0
                });
              });

            case 13:
            case "end":
              return _context3.stop();
          }
        }
      }, _callee3, null, [[3, 10]]);
    }));

    return function listObjects() {
      return _ref2.apply(this, arguments);
    };
  }();

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
  $scope.addFolder = /*#__PURE__*/_asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee4() {
    var withoutLeadTrailSlash, folder, params, canCreate;
    return _regeneratorRuntime().wrap(function _callee4$(_context4) {
      while (1) {
        switch (_context4.prev = _context4.next) {
          case 0:
            withoutLeadTrailSlash = $scope.model.newFolder.replace(/^\/+/g, '').replace(/\/+$/g, '');
            folder = $scope.model.currentPrefix + withoutLeadTrailSlash + '/';
            params = {
              Bucket: $scope.model.bucket,
              Key: folder
            };
            canCreate = false; // Slightly awkward since a 404 is converted to an exception

            _context4.prev = 4;
            _context4.next = 7;
            return s3.headObject(params).promise();

          case 7:
            _context4.next = 15;
            break;

          case 9:
            _context4.prev = 9;
            _context4.t0 = _context4["catch"](4);
            canCreate = _context4.t0.code === 'NotFound';

            if (canCreate) {
              _context4.next = 15;
              break;
            }

            alert('Error creating folder: ' + _context4.t0);
            return _context4.abrupt("return");

          case 15:
            if (canCreate) {
              _context4.next = 18;
              break;
            }

            alert('Error: folder or object already exists at ' + params.Key);
            return _context4.abrupt("return");

          case 18:
            _context4.prev = 18;
            _context4.next = 21;
            return s3.putObject(params).promise();

          case 21:
            _context4.next = 26;
            break;

          case 23:
            _context4.prev = 23;
            _context4.t1 = _context4["catch"](18);
            alert('Error creating folder: ' + _context4.t1);

          case 26:
            $scope.$broadcast('modal::close::add-folder');
            $rootScope.$broadcast('reload-object-list');
            $scope.model.newFolder = '';

          case 29:
          case "end":
            return _context4.stop();
        }
      }
    }, _callee4, null, [[4, 9], [18, 23]]);
  }));
});
angular.module('aws-js-s3-explorer').controller('UploadController', function (s3, $scope, $rootScope) {
  function queue(concurrency) {
    var running = 0;
    var tasks = [];
    return /*#__PURE__*/function () {
      var _run = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee5(task) {
        return _regeneratorRuntime().wrap(function _callee5$(_context5) {
          while (1) {
            switch (_context5.prev = _context5.next) {
              case 0:
                tasks.push(task);

                if (!(running >= concurrency)) {
                  _context5.next = 3;
                  break;
                }

                return _context5.abrupt("return");

              case 3:
                ++running;

              case 4:
                if (!tasks.length) {
                  _context5.next = 15;
                  break;
                }

                _context5.prev = 5;
                _context5.next = 8;
                return tasks.shift()();

              case 8:
                _context5.next = 13;
                break;

              case 10:
                _context5.prev = 10;
                _context5.t0 = _context5["catch"](5);
                console.error(_context5.t0);

              case 13:
                _context5.next = 4;
                break;

              case 15:
                --running;

              case 16:
              case "end":
                return _context5.stop();
            }
          }
        }, _callee5, null, [[5, 10]]);
      }));

      function run(_x4) {
        return _run.apply(this, arguments);
      }

      return run;
    }();
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

      model.queue( /*#__PURE__*/_asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee6() {
        var upload;
        return _regeneratorRuntime().wrap(function _callee6$(_context6) {
          while (1) {
            switch (_context6.prev = _context6.next) {
              case 0:
                _context6.prev = 0;

                if (model.aborted) {
                  _context6.next = 6;
                  break;
                }

                upload = s3.upload(params, {
                  queueSize: model.connectionsPerFile
                });
                model.uploads.push(upload);
                _context6.next = 6;
                return upload.on('httpUploadProgress', onProgress).promise();

              case 6:
                _context6.next = 11;
                break;

              case 8:
                _context6.prev = 8;
                _context6.t0 = _context6["catch"](0);

                if (!model.aborted) {
                  console.error(_context6.t0);
                  $scope.$apply(function () {
                    file.error = _context6.t0.code || _context6.t0.message || _context6.t0;
                  });
                }

              case 11:
                _context6.prev = 11;
                --model.remaining;
                return _context6.finish(11);

              case 14:
                if (model.remaining == 0) {
                  $scope.$apply();
                  $rootScope.$broadcast('reload-object-list');
                }

              case 15:
              case "end":
                return _context6.stop();
            }
          }
        }, _callee6, null, [[0, 8, 11, 14]]);
      })));
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
    var errors = objEntries(err || {}).map(function (_ref5) {
      var _ref6 = _slicedToArray(_ref5, 2),
          key = _ref6[0],
          value = _ref6[1];

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
  $scope.deleteFiles = /*#__PURE__*/_asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee7() {
    var model, _Deleter, _Deleter2, scheduleDelete, flushDelete, setObjectMessage, i, prefix, continuationToken, isTruncated, _response, j, updateObject, processResponse, _i4;

    return _regeneratorRuntime().wrap(function _callee7$(_context7) {
      while (1) {
        switch (_context7.prev = _context7.next) {
          case 0:
            model = $scope.model;
            model.trashing = true;
            _Deleter = Deleter(s3, model.bucket), _Deleter2 = _slicedToArray(_Deleter, 2), scheduleDelete = _Deleter2[0], flushDelete = _Deleter2[1]; // Slight hack to ensure that we are no longer in a digest, to make
            // each iteration of the below loop able to assume it's not in a digest

            _context7.next = 5;
            return new Promise(function (resolve) {
              return window.setTimeout(resolve);
            });

          case 5:
            setObjectMessage = function setObjectMessage(obj, messageKey, messageText) {
              if (!model.aborted) {
                $scope.$apply(function () {
                  obj[messageKey] = messageText;
                });
              }
            }; // Delete prefixes: fetch all keys under them, deleting as we go to avoid storing in memory


            i = 0;

          case 7:
            if (!(i < model.prefixes.length && !model.aborted)) {
              _context7.next = 56;
              break;
            }

            prefix = model.prefixes[i];
            setObjectMessage(prefix, 'deleteStarted', true); // Attempt to list objects under the prefix. If the list objects
            // call fails, update the model and try the next prefix.

            continuationToken = null;
            isTruncated = true;

          case 12:
            if (!(isTruncated && !model.aborted)) {
              _context7.next = 43;
              break;
            }

            _response = void 0;
            _context7.prev = 14;
            _context7.next = 17;
            return s3.listObjectsV2({
              Bucket: model.bucket,
              Prefix: prefix.Prefix,
              ContinuationToken: continuationToken
            }).promise();

          case 17:
            _response = _context7.sent;
            continuationToken = _response.NextContinuationToken;
            isTruncated = _response.IsTruncated;
            _context7.next = 27;
            break;

          case 22:
            _context7.prev = 22;
            _context7.t0 = _context7["catch"](14);
            console.error(_context7.t0);
            setObjectMessage(prefix, 'deleteError', _context7.t0.code || _context7.t0.message || _context7.t0);
            return _context7.abrupt("continue", 12);

          case 27:
            j = 0;

          case 28:
            if (!(j < _response.Contents.length && !model.aborted)) {
              _context7.next = 41;
              break;
            }

            _context7.prev = 29;
            _context7.next = 32;
            return scheduleDelete(_response.Contents[j].Key);

          case 32:
            _context7.next = 38;
            break;

          case 34:
            _context7.prev = 34;
            _context7.t1 = _context7["catch"](29);
            setObjectMessage(prefix, 'deleteError', _context7.t1.code || _context7.t1.message || _context7.t1);
            return _context7.abrupt("break", 41);

          case 38:
            ++j;
            _context7.next = 28;
            break;

          case 41:
            _context7.next = 12;
            break;

          case 43:
            _context7.prev = 43;
            _context7.next = 46;
            return flushDelete();

          case 46:
            _context7.next = 52;
            break;

          case 48:
            _context7.prev = 48;
            _context7.t2 = _context7["catch"](43);
            setObjectMessage(prefix, 'deleteError', _context7.t2.code || _context7.t2.message || _context7.t2);
            return _context7.abrupt("continue", 53);

          case 52:
            setObjectMessage(prefix, 'deleteFinished', true);

          case 53:
            ++i;
            _context7.next = 7;
            break;

          case 56:
            // Delete objects
            // Find an object by key in the model's list of objects
            updateObject = function updateObject(key, messageKey, message) {
              var objs = model.objects.filter(function (o) {
                return o.Key === key;
              });

              if (objs.length > 0) {
                setObjectMessage(objs[0], messageKey, message);
              }
            }; // Process the bulk delete response from s3.
            // Sets the `deleteFinished` or `deleteError` attribute accordingly


            processResponse = function processResponse(response) {
              if (typeof response === 'undefined') return; // Update objects that were successfully deleted

              for (var _i2 = 0; _i2 < response.Deleted.length; _i2++) {
                updateObject(response.Deleted[_i2].Key, 'deleteFinished', true);
              } // Update objects that had errors


              for (var _i3 = 0; _i3 < response.Errors.length; _i3++) {
                updateObject(response.Errors[_i3].Key, 'deleteError', response.Errors[_i3].Code || response.Errors[_i3].Message);
              }
            };

            _i4 = 0;

          case 59:
            if (!(_i4 < model.objects.length && !model.aborted)) {
              _context7.next = 68;
              break;
            }

            _context7.t3 = processResponse;
            _context7.next = 63;
            return scheduleDelete(model.objects[_i4].Key);

          case 63:
            _context7.t4 = _context7.sent;
            (0, _context7.t3)(_context7.t4);

          case 65:
            ++_i4;
            _context7.next = 59;
            break;

          case 68:
            _context7.t5 = processResponse;
            _context7.next = 71;
            return flushDelete();

          case 71:
            _context7.t6 = _context7.sent;
            (0, _context7.t5)(_context7.t6);
            setObjectMessage($scope.model, 'finished', true);
            $rootScope.$broadcast('reload-object-list');

          case 75:
          case "end":
            return _context7.stop();
        }
      }
    }, _callee7, null, [[14, 22], [29, 34], [43, 48]]);
  }));
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
  function entries(_x5) {
    return _entries.apply(this, arguments);
  }

  function _entries() {
    _entries = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee9(directoryReader) {
      var entries, latestEntries;
      return _regeneratorRuntime().wrap(function _callee9$(_context9) {
        while (1) {
          switch (_context9.prev = _context9.next) {
            case 0:
              entries = [];

            case 1:
              if (!true) {
                _context9.next = 10;
                break;
              }

              _context9.next = 4;
              return new Promise(function (resolve, reject) {
                directoryReader.readEntries(resolve, reject);
              });

            case 4:
              latestEntries = _context9.sent;

              if (!(latestEntries.length == 0)) {
                _context9.next = 7;
                break;
              }

              return _context9.abrupt("break", 10);

            case 7:
              entries = entries.concat(latestEntries);
              _context9.next = 1;
              break;

            case 10:
              return _context9.abrupt("return", entries);

            case 11:
            case "end":
              return _context9.stop();
          }
        }
      }, _callee9);
    }));
    return _entries.apply(this, arguments);
  }

  function file(_x6) {
    return _file.apply(this, arguments);
  }

  function _file() {
    _file = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee10(fileEntry) {
      var file;
      return _regeneratorRuntime().wrap(function _callee10$(_context10) {
        while (1) {
          switch (_context10.prev = _context10.next) {
            case 0:
              _context10.next = 2;
              return new Promise(function (resolve, reject) {
                fileEntry.file(resolve, reject);
              });

            case 2:
              file = _context10.sent;
              // We monkey-patch the file to include its FileSystemEntry fullPath,
              // which is a path relative to the root of the pseudo-filesystem of
              // a dropped folder
              file.relativePath = fileEntry.fullPath.substring(1); // Remove leading slash

              return _context10.abrupt("return", file);

            case 5:
            case "end":
              return _context10.stop();
          }
        }
      }, _callee10);
    }));
    return _file.apply(this, arguments);
  }

  function getFiles(_x7) {
    return _getFiles.apply(this, arguments);
  }

  function _getFiles() {
    _getFiles = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee11(dataTransferItemList) {
      var files, i, entry, _fileAndDirectoryEntr;

      return _regeneratorRuntime().wrap(function _callee11$(_context11) {
        while (1) {
          switch (_context11.prev = _context11.next) {
            case 0:
              files = []; // DataTransferItemList does not support map

              fileAndDirectoryEntryQueue = [];

              for (i = 0; i < dataTransferItemList.length; ++i) {
                // At the time of writing no browser supports `getAsEntry`
                fileAndDirectoryEntryQueue.push(dataTransferItemList[i].webkitGetAsEntry());
              }

            case 3:
              if (!(fileAndDirectoryEntryQueue.length > 0)) {
                _context11.next = 24;
                break;
              }

              entry = fileAndDirectoryEntryQueue.shift();

              if (!entry.isFile) {
                _context11.next = 13;
                break;
              }

              _context11.t0 = files;
              _context11.next = 9;
              return file(entry);

            case 9:
              _context11.t1 = _context11.sent;

              _context11.t0.push.call(_context11.t0, _context11.t1);

              _context11.next = 22;
              break;

            case 13:
              if (!entry.isDirectory) {
                _context11.next = 22;
                break;
              }

              _context11.t2 = (_fileAndDirectoryEntr = fileAndDirectoryEntryQueue).push;
              _context11.t3 = _fileAndDirectoryEntr;
              _context11.t4 = _toConsumableArray;
              _context11.next = 19;
              return entries(entry.createReader());

            case 19:
              _context11.t5 = _context11.sent;
              _context11.t6 = (0, _context11.t4)(_context11.t5);

              _context11.t2.apply.call(_context11.t2, _context11.t3, _context11.t6);

            case 22:
              _context11.next = 3;
              break;

            case 24:
              return _context11.abrupt("return", files);

            case 25:
            case "end":
              return _context11.stop();
          }
        }
      }, _callee11);
    }));
    return _getFiles.apply(this, arguments);
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

      function broadcastFiles(_x8) {
        return _broadcastFiles.apply(this, arguments);
      }

      function _broadcastFiles() {
        _broadcastFiles = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee8(event) {
          var files;
          return _regeneratorRuntime().wrap(function _callee8$(_context8) {
            while (1) {
              switch (_context8.prev = _context8.next) {
                case 0:
                  event.stopPropagation();
                  event.preventDefault();
                  _context8.next = 4;
                  return getFiles(event.dataTransfer.items);

                case 4:
                  files = _context8.sent;
                  scope.$apply(function () {
                    scope.$broadcast('dropzone::files', files);
                  });

                case 6:
                case "end":
                  return _context8.stop();
              }
            }
          }, _callee8);
        }));
        return _broadcastFiles.apply(this, arguments);
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

  function deleteKeys() {
    return _deleteKeys.apply(this, arguments);
  }

  function _deleteKeys() {
    _deleteKeys = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee12() {
      var response;
      return _regeneratorRuntime().wrap(function _callee12$(_context12) {
        while (1) {
          switch (_context12.prev = _context12.next) {
            case 0:
              _context12.prev = 0;
              _context12.next = 3;
              return s3.deleteObjects({
                Bucket: bucket,
                Delete: {
                  Objects: keys
                }
              }).promise();

            case 3:
              response = _context12.sent;
              _context12.next = 10;
              break;

            case 6:
              _context12.prev = 6;
              _context12.t0 = _context12["catch"](0);
              console.error(_context12.t0);
              throw _context12.t0;

            case 10:
              _context12.prev = 10;
              keys = [];
              return _context12.finish(10);

            case 13:
              return _context12.abrupt("return", response);

            case 14:
            case "end":
              return _context12.stop();
          }
        }
      }, _callee12, null, [[0, 6, 10, 13]]);
    }));
    return _deleteKeys.apply(this, arguments);
  }

  function scheduleDelete(_x9) {
    return _scheduleDelete.apply(this, arguments);
  }

  function _scheduleDelete() {
    _scheduleDelete = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee13(key) {
      return _regeneratorRuntime().wrap(function _callee13$(_context13) {
        while (1) {
          switch (_context13.prev = _context13.next) {
            case 0:
              keys.push({
                Key: key
              });

              if (!(keys.length >= bulkDeleteMaxFiles)) {
                _context13.next = 5;
                break;
              }

              _context13.next = 4;
              return deleteKeys();

            case 4:
              return _context13.abrupt("return", _context13.sent);

            case 5:
            case "end":
              return _context13.stop();
          }
        }
      }, _callee13);
    }));
    return _scheduleDelete.apply(this, arguments);
  }

  function flushDelete() {
    return _flushDelete.apply(this, arguments);
  }

  function _flushDelete() {
    _flushDelete = _asyncToGenerator( /*#__PURE__*/_regeneratorRuntime().mark(function _callee14() {
      return _regeneratorRuntime().wrap(function _callee14$(_context14) {
        while (1) {
          switch (_context14.prev = _context14.next) {
            case 0:
              if (!keys.length) {
                _context14.next = 4;
                break;
              }

              _context14.next = 3;
              return deleteKeys();

            case 3:
              return _context14.abrupt("return", _context14.sent);

            case 4:
            case "end":
              return _context14.stop();
          }
        }
      }, _callee14);
    }));
    return _flushDelete.apply(this, arguments);
  }

  return [scheduleDelete, flushDelete];
}