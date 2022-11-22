const richTextConfig = {
  heading: {
    options: [
      {
        model: "paragraph",
        title: "Paragraph",
        view: {
          name: "p",
          classes: "govuk-body",
        },
      },
      {
        model: "heading3",
        title: "Heading 3",
        view: {
          name: "h3",
          classes: "govuk-heading-l",
        },
      },
      {
        model: "heading4",
        title: "Heading 4",
        view: {
          name: "h4",
          classes: "govuk-heading-m",
        },
      },
      {
        model: "heading5",
        title: "Heading 5",
        view: {
          name: "h5",
          classes: "govuk-heading-s",
        },
      },
      {
        model: "heading6",
        title: "Heading 6",
        view: {
          name: "h6",
          classes: "govuk-heading-xs",
        },
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
document.addEventListener("DOMContentLoaded", function () {
  const textAreas = Array.prototype.slice.call(
    document.querySelectorAll("textarea[data-type=rich-text-editor]")
  );
  for (let i = 0; i < textAreas.length; ++i) {
    ClassicEditor.create(textAreas[i], richTextConfig).catch((error) => {
      console.error(error);
    });
  }
});
