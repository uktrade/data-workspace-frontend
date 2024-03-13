const richTextConfig = {
  heading: {
    options: [
      {
        model: "govukParagraph",
        title: "Paragraph",
        view: {
          name: "p",
          classes: ["govuk-body"],
        },
        class: "govuk-body",
      },
      {
        model: "heading3",
        title: "Heading 3",
        view: {
          name: "h3",
          classes: ["govuk-heading-m"],
        },
        class: "govuk-heading-m",
      },
      {
        model: "heading4",
        title: "Heading 4",
        view: {
          name: "h4",
          classes: ["govuk-heading-s"],
        },
        class: "govuk-heading-s",
      },
    ],
  },
  codeBlock: {
    languages: [
      { language: "bash", label: "Bash" },
      { language: "javascript", label: "JSON" },
      { language: "python", label: "Python" },
      { language: "r", label: "R" },
      { language: "pgsql", label: "SQL" },
    ],
  },
  style: {
    definitions: [
      {
        name: "Link",
        element: "a",
        classes: ["govuk-link"],
      },
    ],
  },
  link: {
    decorators: [
      {
        mode: "automatic",
        callback: function () {
          return true;
        },
        attributes: {
          class: "govuk-link",
        },
      },
    ],
  },
};

let editors = {};

document.addEventListener('DOMContentLoaded', function () {
  const textAreas = Array.prototype.slice.call(
    document.querySelectorAll('textarea[data-type=rich-text-editor]')
  );

  let editorPromises = textAreas.map((textArea) =>
    ClassicEditor.create(textArea, richTextConfig).then((editor) => {
      editors[textArea.id] = editor;
    })
  );

  Promise.all(editorPromises)
    .then(() => {
      for (let id in editors) {
        editors[id].model.document.on('change', () => {
          const preElements = document.querySelectorAll('pre');

          preElements.forEach(function (pre) {
            const code = pre.querySelector('code[class^="language-"]');
            if (code) {
              const language = code.className.replace('language-', '');
              pre.setAttribute('aria-label', language);
            }
          });
        });
      }
    })
    .catch((error) => {
      console.error(error);
    });
});
