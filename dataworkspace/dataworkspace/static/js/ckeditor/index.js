// eslint-disable-next-line simple-import-sort/imports
import {
  ClassicEditor,
  Essentials,
  Bold,
  Italic,
  Heading,
  Link
} from 'ckeditor5';

import 'ckeditor5/ckeditor5.css';

document.addEventListener('DOMContentLoaded', () => {
  document
    .querySelectorAll('textarea[data-type="rich-text-editor"]')
    .forEach((selector) => {
      ClassicEditor.create(selector, {
        plugins: [Essentials, Bold, Italic, Heading, Link],
        toolbar: {
          items: ['undo', 'redo', '|', 'bold', 'italic', '|', 'heading', 'link']
        }
      }).catch((error) => {
        // eslint-disable-next-line no-console
        console.error(error.stack);
      });
    });

  document
    .querySelectorAll('textarea[data-type="rich-text-editor-link-only"]')
    .forEach((selector) => {
      ClassicEditor.create(selector, {
        plugins: [Essentials, Heading, Link],
        toolbar: {
          items: ['link']
        }
      }).catch((error) => {
        // eslint-disable-next-line no-console
        console.error(error.stack);
      });
    });
});
