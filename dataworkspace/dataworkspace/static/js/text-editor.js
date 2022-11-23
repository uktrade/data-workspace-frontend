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
