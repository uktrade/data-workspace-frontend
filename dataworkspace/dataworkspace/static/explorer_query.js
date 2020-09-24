// SQL Editor
import * as ace from 'ace-builds'
import 'ace-builds/src-noconflict/mode-sql'
import 'ace-builds/src-noconflict/theme-chrome'
import 'ace-builds/src-noconflict/ext-language_tools'
import sqlFormatter from "sql-formatter";

var editor = ace.edit("ace-sql-editor", {
  mode: "ace/mode/sql",
  theme: "ace/theme/chrome",
  maxLines: 10,
  minLines: 10,
  fontSize: 18,
  showLineNumbers: false,
  showGutter: false,
  enableLiveAutocompletion: true,
  showPrintMargin: false,
  readOnly: document.getElementById('ace-sql-editor').dataset.disabled || false,
});

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
