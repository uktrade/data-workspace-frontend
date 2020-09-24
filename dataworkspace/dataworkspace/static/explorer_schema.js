import List from 'list.js';


// Slight hack to support up to 100 column names in the search. List.JS expects each searchable datapoint within
// a record to have a unique class.
var numSupportedColumns = 100;
var columnClasses = ['js-schema-table']
for (var i = 0; i < numSupportedColumns; i++) {
  columnClasses.push('js-schema-column-' + (i+1));
}

var tableList = new List('js-tables', {
  indexAsync: true,
  listClass: "js-list",
  searchClass: "js-search",
  valueNames: columnClasses,
});
