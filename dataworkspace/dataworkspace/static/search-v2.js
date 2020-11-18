(function ($) {
  "use strict";

  var ToggleInputClassOnFocus = function ($el) {
    var $toggleTarget = $el.find('.js-class-toggle')

    if (!inputIsEmpty()) {
      addFocusClass()
    }

    $toggleTarget.on('focus', addFocusClass)
    $toggleTarget.on('blur', removeFocusClassFromEmptyInput)

    function inputIsEmpty () {
      return $toggleTarget.val() === ''
    }

    function addFocusClass () {
      $toggleTarget.addClass('focus')
    }

    function removeFocusClassFromEmptyInput () {
      if (inputIsEmpty()) {
        $toggleTarget.removeClass('focus')
      }
    }
  }

  var LiveSearch = function(formSelector, wrapperSelector, GTM){
    this.wrapperSelector = wrapperSelector;
    this.$wrapper = $(wrapperSelector);
    this.$form = $(formSelector);

    this.state = false;
    this.previousState = false;
    this.resultsCache = {};
    this.GTM = GTM;

    this.originalState = this.$form.serializeArray();
    this.saveState();

    this.$form.on(
      'change', 'input[type=checkbox], input[type=search], select',
      this.formChange.bind(this)
    );
    $(window).on('popstate', this.popState.bind(this));

    this.$form.find('input[type=submit]').click(
      function(e){
        this.formChange();
        e.preventDefault();
      }.bind(this)
    );

    this.$form.find('input[type=search]').keypress(
      function(e){
        if(e.keyCode == 13) {
          // 13 is the return key
          this.formChange();
          e.preventDefault();
        }
      }.bind(this)
    );

    this.$form.find('select').change(
      function(e){
        this.formChange();
        e.preventDefault();
      }.bind(this)
    );
  }

  LiveSearch.prototype.saveState = function saveState(state){
    if(typeof state === 'undefined'){
      state = this.$form.serializeArray();
    }
    this.previousState = this.state;
    this.state = state;
  };

  LiveSearch.prototype.popState = function popState(event){
    if(event.originalEvent.state){
      this.saveState(event.originalEvent.state);
    } else {
      this.saveState(this.originalState);
    }

    this.restoreBooleans();
    this.restoreSearchInputs();
    this.restoreSortSelect();
    this.updateResults();
  };

  LiveSearch.prototype.formChange = function formChange(e){
    var pageUpdated;
    if(this.isNewState()){
      this.saveState();
      pageUpdated = this.updateResults();
      pageUpdated.done(
        function(){
          if (typeof(this.GTM) !== 'undefined') {this.GTM.pushSearchEvent();}
          
          var newPath = window.location.origin + this.$form.attr('action') + "?" + $.param(this.state);
          history.pushState(this.state, '', newPath);
        }.bind(this)
      );
    }
  };

  LiveSearch.prototype.cache = function cache(slug, data) {
    if(typeof data === 'undefined'){
      return this.resultsCache[slug];
    } else {
      this.resultsCache[slug] = data;
    }
  };

  LiveSearch.prototype.isNewState = function isNewState(){
    return $.param(this.state) !== this.$form.serialize();
  };

  LiveSearch.prototype.updateResults = function updateResults(){
    this.showLoadingIndicators();

    var self = this;
    var searchState = $.param(this.state);
    var liveState = this.$form.serializeArray();
    var cachedResultData = this.cache(searchState);

    if(typeof(cachedResultData) === 'undefined') {
      return $.ajax({
        url: this.$form.attr('action'),
        data: $.param(liveState),
        searchState: searchState
      }).done(function(response){
        self.cache(this.searchState, response);
        self.displayFilterResults(response, this.searchState);
      }).fail(function(response){
        self.showErrorIndicator();
      });
    } else {
      this.displayFilterResults(cachedResultData, searchState);
      var out = new $.Deferred();
      return out.resolve();
    }
  };

  LiveSearch.prototype.showLoadingIndicators = function showLoadingIndicators() {
    this.$wrapper.css('opacity', '0.25')
  }

  LiveSearch.prototype.showErrorIndicator = function showErrorIndicator() {
    this.$wrapper.text('Error. Please try modifying your search and trying again.');
  }

  LiveSearch.prototype.displayFilterResults = function displayFilterResults(response, state) {
    if(state == $.param(this.state) && state !== "") {
      this.replaceBlock(this.wrapperSelector, $(response).find(this.wrapperSelector).html());
    }

    this.$wrapper.css('opacity', '1')

    if (window.installFilterShowMore !== undefined) {
        // Hook into app-filter-show-more-v2.js to un-hide the "show more" button on search filters.
        window.installFilterShowMore();
    }
  }

  LiveSearch.prototype.replaceBlock = function replaceBlock(selector, html) {
    $(selector).html(html);
  }

  LiveSearch.prototype.restoreBooleans = function restoreBooleans(){
    var that = this;
    this.$form.find('input[type=checkbox], input[type=radio]').each(function(i, el){
      var $el = $(el);
      $el.prop('checked', that.isBooleanSelected($el.attr('name'), $el.attr('value')));
    });
  };

  LiveSearch.prototype.isBooleanSelected = function isBooleanSelected(name, value){
    var i, _i;
    for(i=0,_i=this.state.length; i<_i; i++){
      if(this.state[i].name === name && this.state[i].value === value){
        return true;
      }
    }
    return false;
  };

  LiveSearch.prototype.restoreSearchInputs = function restoreSearchInputs(){
    var that = this;
    this.$form.find('input[type=search]').each(function(i, el){
      var $el = $(el);
      $el.val(that.getTextInputValue($el.attr('name')));
    });
  };

  LiveSearch.prototype.restoreSortSelect = function restoreSortSelect(){
    var that = this;
    this.$form.find('select').each(function(i, el){
      var $el = $(el);
      $el.val(that.getTextInputValue($el.attr('name')));
    });
  };

  LiveSearch.prototype.getTextInputValue = function getTextInputValue(name){
    var i, _i;
    for(i=0,_i=this.state.length; i<_i; i++){
      if(this.state[i].name === name){
        return this.state[i].value
      }
    }
    return '';
  };


  $(document).ready(function() {
    var form = new LiveSearch('#live-search-form', '#live-search-wrapper', new GTMDatasetSearchSupport());
    var searchInput = new ToggleInputClassOnFocus($("#live-search-form"))
  });
})(jQuery);
