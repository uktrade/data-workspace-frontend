import {
  ILauncher,
} from "@jupyterlab/launcher";

import {
  IFileBrowserFactory,
} from "@jupyterlab/filebrowser";

import {
  Widget,
} from "@phosphor/widgets";

import {
  Dialog, showDialog,
} from "@jupyterlab/apputils";

export default {
  activate: (app, launcher, browser) => {
    const open_command = 'jupyterlab_template_access:open';

    app.commands.addCommand(open_command, {
      label: 'Template',
      caption: 'Open a new notebook from a list of pre-defined templates',
      execute: async (args) => {
        const dialog_result = await showDialog({
          body: new OpenDialogContents(),
          buttons: [Dialog.cancelButton(), Dialog.okButton({ label: 'Open' })],
          focusNodeSelector: 'select',
          title: 'Template'
        });
        if (dialog_result.button.label === 'CANCEL') return;

        const template_response = await fetch(dialog_result.value);
        const model = await app.commands.execute(
          'docmanager:new-untitled',
          {path: browser.defaultBrowser.model.path, type:'notebook'}
        );
        const widget = await app.commands.execute('docmanager:open', {
          factory: 'Notebook', path: model.path
        });

        await widget.context.ready;
        widget.model.fromString(await template_response.text());

        return widget;
      }
    });

    launcher.add({
      args: {isLauncher: true, kernelName: 'template'},
      category: 'Notebook',
      command: open_command,
      // FontAwesome https://fontawesome.com/license
      kernelIconUrl: "data:image/svg+xml,%3Csvg aria-hidden='true' focusable='false' data-prefix='fas' data-icon='cubes' class='svg-inline--fa fa-cubes fa-w-16' role='img' xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Cpath fill='rgb(237,108,31)' d='M488.6 250.2L392 214V105.5c0-15-9.3-28.4-23.4-33.7l-100-37.5c-8.1-3.1-17.1-3.1-25.3 0l-100 37.5c-14.1 5.3-23.4 18.7-23.4 33.7V214l-96.6 36.2C9.3 255.5 0 268.9 0 283.9V394c0 13.6 7.7 26.1 19.9 32.2l100 50c10.1 5.1 22.1 5.1 32.2 0l103.9-52 103.9 52c10.1 5.1 22.1 5.1 32.2 0l100-50c12.2-6.1 19.9-18.6 19.9-32.2V283.9c0-15-9.3-28.4-23.4-33.7zM358 214.8l-85 31.9v-68.2l85-37v73.3zM154 104.1l102-38.2 102 38.2v.6l-102 41.4-102-41.4v-.6zm84 291.1l-85 42.5v-79.1l85-38.8v75.4zm0-112l-102 41.4-102-41.4v-.6l102-38.2 102 38.2v.6zm240 112l-85 42.5v-79.1l85-38.8v75.4zm0-112l-102 41.4-102-41.4v-.6l102-38.2 102 38.2v.6z'%3E%3C/path%3E%3C/svg%3E"
     });
  },
  id: 'jupyterlab_template_access',
  requires: [ILauncher, IFileBrowserFactory],
  autoStart: true
};

class OpenDialogContents extends Widget {
  constructor() {
    const body = document.createElement('div');
    const select = document.createElement('select');

    // Immediately invoked function since a constructor can't be async
    (async () => {
      const response = await fetch('/templates/');
      (await response.json())['templates'].forEach((template) => {
        const option = document.createElement('option');
        option.label = template.name;
        option.text  = template.name;
        option.value = template.path;
        select.appendChild(option);
      });
    })();

    body.appendChild(select);
    super({ node: body });
  }

  getValue() {
    return this.inputNode.value;
  }

  get inputNode() {
    return this.node.getElementsByTagName("select")[0];
  }
}
