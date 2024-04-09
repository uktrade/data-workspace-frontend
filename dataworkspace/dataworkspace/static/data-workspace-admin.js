jQuery = window.django.jQuery;

jQuery(function () {
  jQuery(".field-data_type select").on("change", function () {
    var relationSelector = jQuery(this)
      .parents("tr")
      .find(".field-linked_reference_dataset select");
    if (jQuery(this).val() != 8) {
      relationSelector.val(null);
      relationSelector.attr("disabled", "disabled");
    } else {
      relationSelector.removeAttr("disabled");
    }
  });
});

jQuery(function () {
  let _changed = false;
  let nameInput = jQuery('#referencedataset_form input[name="name"]');
  let tableNameInput = jQuery(
    '#referencedataset_form input[name="table_name"]'
  );
  nameInput.on("keyup", function () {
    if (_changed == false) {
      let tableName;
      let urlified = URLify(jQuery(this).val());
      if (urlified == "") {
        tableName = "";
      } else {
        tableName = `ref_${urlified.split("-").join("_")}`;
      }
      tableNameInput.val(tableName);
    }
  });
  tableNameInput.on("keyup", function () {
    _changed = true;
  });

  jQuery(".field-name input").on("keyup", function () {
    let name = jQuery(this).attr("name");
    let index = name.match(/(?!=fields-)[0-9]+(?=-name)/);
    let columnField = jQuery(
      `.field-column_name input[name="fields-${index}-column_name"]`
    );
    if (!columnField[0].hasAttribute("_change")) {
      columnField.attr("_change", 0);
    }

    if (
      parseInt(columnField.attr("_change")) == 0 &&
      columnField.attr("disabled") !== "disabled"
    ) {
      let columnName;
      let urlified = URLify(jQuery(this).val());
      if (urlified == "") {
        columnName = "";
      } else {
        columnName = urlified.split("-").join("_");
      }
      columnField.val(columnName);
    }
  });

  jQuery(".field-column_name input").on("keyup", function () {
    jQuery(this).attr("_change", 1);
  });
});
