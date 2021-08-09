/**
 * calls vega lite to generate an image using the config/data
 *
 * @param dataUrl - url to request the data.
 * @param csrfToken - django csrfToken
 * @param viewElementId - the #elementId. NB: The preceeding hash # is required!
 */
function buildVisualisation(dataUrl, viewElementId) {
  if (!dataUrl) throw "dataUrl is required";
  if (!viewElementId) throw "viewElementId is required";

  function getVegaConfig(dataUrl) {
    return new Promise(function (resolve, reject) {
      fetch(dataUrl, {
        method: "GET",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-Requested-With": "XMLHttpRequest",
        },
      })
        .then(function (response) {
          return response.json();
        })
        .then(function (json) {
          resolve(json);
        })
        .catch(function (err) {
          console.error(err);
          reject(err);
        });
    });
  }

  return getVegaConfig(dataUrl).then(function (vegaSpec) {
    var actions = {
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
