/**
 * calls vega lite to generate an image using the config/data returned from *POST* to dataUrl
 *
 * @param dataUrl - url to request the data.
 * @param csrfToken - django csrfToken
 * @param viewElementId - the #elementId. NB: The preceeding hash # is required!
 */
function buildVisualisation(dataUrl, csrfToken, viewElementId) {
  if (!dataUrl) throw "dataUrl is required";
  if (!csrfToken) throw "csrfToken is required";

  function getVegaConfig(dataUrl, csrfToken) {

    return new Promise((resolve, reject) => {
      fetch(dataUrl, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
          "X-CSRFToken": csrfToken,
        },
      })
        .then((response) => {
          return response.json();
        })
        .then((json) => {
          resolve(json);
        })
        .catch((err) => {
          console.error(err);
          reject(err);
        });
    });
  }

  return getVegaConfig(dataUrl, csrfToken).then((vegaSpec) => {
    const actions = {
      export: true,
      source: false,
      compiled: false,
      editor: false,
    };

    // return so the client can get access to view etc
    return vegaEmbed(viewElementId, vegaSpec, {
      actions: actions,
      ast: true,
    });
  });
}
