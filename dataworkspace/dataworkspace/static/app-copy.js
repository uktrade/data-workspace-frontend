function nodeListForEach (nodes, callback) {
  if (window.NodeList.prototype.forEach) {
    return nodes.forEach(callback)
  }
  for (var i = 0; i < nodes.length; i++) {
    callback.call(window, nodes[i], i, nodes)
  }
}

function Copy ($module) {
  this.$module = $module;
  this.$button = null;
}

Copy.prototype.init = function () {
  let $module = this.$module;
  if (!$module) {
    return
  }

  this.$button = document.createElement('button');
  this.$button.id = 'copy-code';
  this.$button.className = 'app-copy-button js-copy-button';
  this.$button.setAttribute('aria-live', 'assertive');
  this.$button.textContent = 'Copy code';
  $module.insertBefore(this.$button, $module.firstChild);

  let that = this;
  this.$button.addEventListener("click", function (e) {
    let copyText = that.$button.nextElementSibling.textContent;
    let interimElement = document.createElement('textarea');
    interimElement.value = copyText;

    document.body.appendChild(interimElement);

    interimElement.select();
    document.execCommand('Copy');
    document.body.removeChild(interimElement);

    that.$button.textContent = "Code copied";

    setTimeout(function () {
      that.$button.textContent = 'Copy code'
    }, 5000)
  });
};

let $codeBlocks = document.querySelectorAll('[data-module="app-copy"]')
nodeListForEach($codeBlocks, function ($codeBlock) {
  new Copy($codeBlock).init()
});
