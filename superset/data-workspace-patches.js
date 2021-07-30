var STYLE_FILEPATH = '/__mirror/maps/bright/osm-bright-gl-style.json';
var STYLES_RE = /.*?api\.mapbox\.com\/styles.*?/;
var TILES_RE = /^protocol:\/\/host\/.*?/;

(function(window){

  // Patch fetch() calls for the style file and tiles
  var x = window.fetch;
  window.fetch = function() {
    if (arguments[0] instanceof Request) {
      if (STYLES_RE.test(arguments[0].url)) {
        arguments[0] = new Request(window.location.origin + STYLE_FILEPATH, arguments[0])
      }
      else if (TILES_RE.test(arguments[0].url)) {
        arguments[0] = new Request(
          arguments[0].url.replace('protocol://host', window.location.origin),
          arguments[0]
        )
      }
    }
    return x.apply(this, arguments);
  }

  // Patch worker postMessage calls to inject our own glyphs
  var postMessage = Worker.prototype.postMessage
  Worker.prototype.postMessage = function(args) {
    if (args.data instanceof Object && args.data.request instanceof Object) {
      var url = args.data.request.url;
      if (url.startsWith('protocol://host')) {
        args.data.request.url = url.replace('protocol://host', window.location.origin)
      }
    }
    postMessage.call(this, args);
  }

  if (window.location.pathname === '/tablemodelview/list/') {
    /*
     Hide the "create dataset" button on the dataset list view page
     as we don't want users creating physical datasets
     */
    document.head.insertAdjacentHTML(
        'beforeend',
        '<style>nav .navbar-right button:nth-child(2) { display: none !important }</style>'
    )
    /*
      Hide the physical/virtual dataset radio button from the edit dataset modal
     */
    document.head.insertAdjacentHTML(
        'beforeend',
        '<style>.ant-modal-body .ant-radio-wrapper { display: none !important; }</style>'
    )
  }
})(window);
