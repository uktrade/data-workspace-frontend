const richTextConfig = {
  heading: {
    options: [
      {
        model: "paragraph",
        title: "Paragraph",
      },
      {
        model: "heading3",
        view: "h3",
        title: "Heading 3",
      },
      {
        model: "heading4",
        view: "h4",
        title: "Heading 4",
      },
      {
        model: "heading5",
        view: "h5",
        title: "Heading 5",
      },
      {
        model: "heading6",
        view: "h6",
        title: "Heading 6",
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
