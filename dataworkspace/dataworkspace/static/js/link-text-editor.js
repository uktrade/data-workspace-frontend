const linkRichTextConfig = {
  toolbar: ["Link"],
  style: {
    definitions: [
      {
        name: "Link",
        element: "a",
        attributes: {
          class: "govuk-link",
        },
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
    document.querySelectorAll("textarea[data-type=rich-link-text-editor]")
  );
  for (let i = 0; i < textAreas.length; ++i) {
    ClassicEditor.create(textAreas[i], linkRichTextConfig).catch((error) => {
      console.error(error);
    });
  }
});
