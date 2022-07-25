var editor = ace.edit("ace-sql-editor", {
  mode: "ace/mode/sql",
  theme: "ace/theme/chrome",
  maxLines: 40,
  minLines: 10,
  fontSize: 18,
  showLineNumbers: true,
  showGutter: true,
  enableBasicAutocompletion: true,
  enableLiveAutocompletion: true,
  showPrintMargin: false,
  readOnly: document.getElementById('ace-sql-editor').dataset.disabled || false,
});

var table_list = JSON.parse(document.getElementById("schema_tables").textContent);

var staticWordCompleter = {
  identifierRegexps: [/[a-zA-Z_0-9\.]/],  // The default does not include dots
  getCompletions: function(editor, session, pos, prefix, callback) {
      var wordList = table_list

      callback(null, [...wordList.map(function(word) {
          return {
              caption: word,
              value: word,
              meta: "static"
          };
      }), ...session.$mode.$highlightRules.$keywordList.map(function(word) {
          return {
              caption: word,
              value: word,
              meta: 'keyword',
          };
      })
    ]);
  }
}

editor.completers = [staticWordCompleter]

editor.commands.removeCommand(editor.commands.byName.indent);
editor.commands.removeCommand(editor.commands.byName.outdent);

var textarea = document.getElementsByName("sql")[0];
editor.getSession().on("change", function () {
  textarea.value = editor.getSession().getValue();
});

function update() {
  // adjust size to parent box on show schema
  editor.resize()

  // populate default message if required
  var shouldShow = !editor.session.getValue().length;
  var node = editor.renderer.emptyMessageNode;
  if (!shouldShow && node) {
    editor.renderer.scroller.removeChild(editor.renderer.emptyMessageNode);
    editor.renderer.emptyMessageNode = null;
  } else if (shouldShow && !node) {
    node = editor.renderer.emptyMessageNode = document.createElement("div");
    node.textContent = "Write your query here"
    node.className = "ace_emptyMessage"
    node.style.padding = "0 9px"
    node.style.position = "absolute"
    node.style.zIndex = 9
    node.style.opacity = 0.5
    editor.renderer.scroller.appendChild(node);
  }
}

editor.on("input", update);
setTimeout(update, 100);

let sqlTextarea = document.getElementById('original-sql');
if (sqlTextarea !== null) {
  let original_sql = sqlTextarea.textContent;

  let format_button = document.getElementById("format_button");
  if (format_button !== null) {
    document.getElementById("format_button")
      .addEventListener("click", function (e) {
          var sql = editor.getSession().getValue()
          var formatted_sql = sqlFormatter.format(sql)
          editor.getSession().setValue(formatted_sql)
          sqlTextarea.value = formatted_sql
        }
      );
  }

  let unformat_button = document.getElementById("unformat_button");
  if (unformat_button !== null) {
    document.getElementById("unformat_button")
      .addEventListener("click", function (e) {
          sqlTextarea.value = original_sql
        }
      );
  }
}



let tabsContainer = document.getElementById('playground-tabs');
let fullWidthToggle = document.getElementById('full-width');
let normalWidthToggle = document.getElementById('normal-width');
if (tabsContainer !== null && fullWidthToggle !== null && normalWidthToggle !== null) {
  fullWidthToggle.addEventListener('click', function (e) {
    e.preventDefault();

    tabsContainer.classList.remove('govuk-width-container');
    tabsContainer.classList.add('govuk-!-margin-left-5');
    tabsContainer.classList.add('govuk-!-margin-right-5');
    fullWidthToggle.classList.add('govuk-!-display-none');
    normalWidthToggle.classList.remove('govuk-!-display-none');
  });

  normalWidthToggle.addEventListener('click', function (e) {
    e.preventDefault();

    tabsContainer.classList.remove('govuk-!-margin-left-5');
    tabsContainer.classList.remove('govuk-!-margin-right-5');
    tabsContainer.classList.add('govuk-width-container');
    normalWidthToggle.classList.add('govuk-!-display-none');
    fullWidthToggle.classList.remove('govuk-!-display-none');
  });
}
