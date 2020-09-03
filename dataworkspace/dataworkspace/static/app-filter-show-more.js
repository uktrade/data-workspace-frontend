function nodeListForEach (nodes, callback) {
  if (window.NodeList.prototype.forEach) {
    return nodes.forEach(callback)
  }
  for (let i = 0; i < nodes.length; i++) {
    callback.call(window, nodes[i], i, nodes)
  }
}

let showMoreClicked = {};

function FilterShowMore(module) {
  this.module = module;
  this.button = this.module.getElementsByClassName('js-filter-show-more')[0];
}

FilterShowMore.prototype.init = function () {
  if (!this.module || !this.button) {
    return
  }

  if (this.hasBeenRevealed()) {
    this.revealChoices();
  } else {
    let that = this;

    this.button.classList.remove('hidden');
    this.button.addEventListener('click', function () {
      that.revealChoices();
    });
  }
};

FilterShowMore.prototype.hasBeenRevealed = function() {
  return showMoreClicked[this.module.getAttribute('data-show-more-id')] !== undefined;
}

FilterShowMore.prototype.revealChoices = function () {
  this.button.classList.add('hidden');

  let choices = this.module.getElementsByClassName('app-js-hidden');
  for (let i = 0; i < choices.length; i++) {
      $(choices[i]).show();
  }
  showMoreClicked[this.module.getAttribute('data-show-more-id')] = true;
}

function installFilterShowMore() {
  let modules = document.querySelectorAll('[data-module="filter-show-more"]');
  nodeListForEach(modules, function (module) {
    new FilterShowMore(module).init()
  });
}

installFilterShowMore();
