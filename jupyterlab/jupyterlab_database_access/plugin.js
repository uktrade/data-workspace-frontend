import {
  DisposableDelegate
} from '@phosphor/disposable';

import {
  ToolbarButton
} from '@jupyterlab/apputils';

import {
  NotebookActions
} from '@jupyterlab/notebook';

export default {
  activate: (app) => {
    app.docRegistry.addWidgetExtension('Notebook', new ButtonExtension());
  },
  id: 'jupyterlab_database_access:connectButtonPlugin',
  autoStart: true
};

class ButtonExtension {
  createNew(panel, context) {
    const onClick = () => {
      const notebook = panel.content;
      const model = notebook.model;
      const cell = model.contentFactory.createCodeCell({
        cell: {
          source: code[model.defaultKernelName],
          metadata: {
            trusted: true
          }
        }
      });
      model.cells.insert(notebook.activeCellIndex, cell);
      notebook.activeCellIndex--;
      notebook.widgets[notebook.activeCellIndex].inputHidden = true;
      NotebookActions.runAndAdvance(notebook, context.session);
      cell.inputHidden = true;
    };
    const button = new ToolbarButton({
      iconClassName: 'fa fa-database',
      onClick: onClick,
      tooltip: 'Connect to databases'
    });

    panel.toolbar.insertItem(9, 'connectToDatabases', button);
    return new DisposableDelegate(() => {
      button.dispose();
    });
  }
}

const code = {
  'ir': [
    'library(stringr)',
    'library(DBI)',
    'getConn <- function(dsn) {',
    '  user <- str_match(dsn, "user=([a-z0-9_]+)")[2]',
    '  password <- str_match(dsn, "password=([a-zA-Z0-9_]+)")[2]',
    '  port <- str_match(dsn, "port=(\\\\d+)")[2]',
    '  dbname <- str_match(dsn, "dbname=([a-z0-9_\\\\-]+)")[2]',
    '  host <- str_match(dsn, "host=([a-z0-9_\\\\-\\\\.]+)")[2]',
    '  con <- dbConnect(RPostgres::Postgres(), user=user, password=password, host=host, port=port, dbname=dbname)',
    '  return(con)',
    '}',
    'isDsn <- function(name) {',
    '  return(startsWith(name, "DATABASE_DSN__"))',
    '}',
    'niceName <- function(name) {',
    '  return(substring(name, 15))',
    '}',
    'env = Sys.getenv(names=TRUE)',
    'dsns <- env[Vectorize(isDsn)(names(env))]',
    'conn <- Vectorize(getConn)(unname(dsns))',
    'names(conn) <- Vectorize(niceName)(names(dsns))',
    'print(paste("You now have", as.character(length(conn)), "database connections:", sep=" "))',
    'for (name in names(conn)) {',
    '  var_name <- paste("conn", name, sep="_")',
    '  assign(var_name, conn[[c(name)]])',
    '  print(paste(" ", var_name, sep=""))',
    '}',
    'rm(conn,getConn,isDsn,niceName,env,dsns)'
  ].join('\n'),
  'python3': [
    'from os import environ as __environ',
    'from collections import namedtuple as __namedtuple',
    'from psycopg2 import connect as __connect',
    '__dsns = dict((key.split("__")[1], __connect(value)) for (key, value) in __environ.items() if key.startswith("DATABASE_DSN__"))',
    'conn = __namedtuple("Connections", __dsns.keys())(**__dsns)',
    'print("You now have {} database connection{}:".format(len(__dsns.keys()), "s" if len(__dsns.keys()) > 1 else ""))',
    'for key in __dsns.keys():',
    '  print(f"  conn.{key}")',
    'del __dsns',
    'del __environ',
    'del __namedtuple',
    'del __connect'
  ].join('\n')
}
