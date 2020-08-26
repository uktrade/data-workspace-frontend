function nodeListForEach (nodes, callback) {
  if (window.NodeList.prototype.forEach) {
    return nodes.forEach(callback)
  }
  for (let i = 0; i < nodes.length; i++) {
    callback.call(window, nodes[i], i, nodes)
  }
}

function FilterShowMore(module) {
  this.module = module;
  this.button = this.module.getElementsByClassName('js-filter-show-more')[0];
}

FilterShowMore.prototype.init = function () {
  if (!this.module || !this.button) {
    return
  }

  let that = this;

  this.button.classList.remove('hidden');
  this.button.addEventListener('click', function () {
      this.classList.add('hidden');
      let choices = that.module.getElementsByClassName('app-js-hidden');
      for (let i = 0; i < choices.length; i++) {
          $(choices[i]).show();
      }
  });
};

let modules = document.querySelectorAll('[data-module="filter-show-more"]')
nodeListForEach(modules, function (module) {
  new FilterShowMore(module).init()
});
