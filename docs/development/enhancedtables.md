---
title: Enhanced tables
---

# Enhanced tables

Turn an existing govuk styled table into a govuk styled ag-grid grid.

- Allows for sorting columns
- If the user has JavaScript disabled, automatically fall back to the standard govuk table.
- In the future can be enhanced to add column filtering

## Create table

1. Create a gov uk style table and give it the class `enhanced-table`.
2. The table must have one `<thead>` and one `<tbody>`
3. You can optionally add the data attribute `data-size-to-fit` to ensure columns fit the whole width of the table.

```
<table class="govuk-table enhanced-table data-size-to-fit">
  ...
</table>
```

## Configure rows

Configuration for the columns is done on the `<th>` elements via data attributes. The options are:

- `data-sortable` - enable sorting for this column (disabled by default)
- `data-column-type` - use a specific [ag-grid column type](https://www.ag-grid.com/javascript-data-grid/column-definitions/#custom-column-types)
- `data-renderer` - optionally specify the renderer for the column. Only needed for certain data types
  - `data-renderer="htmlRenderer"` - render/sort column as html (mainly used to display buttons or links in a cell)
  - `data-renderer="dateRenderer"` - render/sort column as dates
  - `data-renderer="datetimeRenderer"` - render/sort column as datetimes
- `data-width` - set a width for a column
- `data-min-width` - set a minimum width in pixels for a column
- `data-max-width` - set a maximum width in pixels for a column
- `data-resizable` - allow resizing of the column (disabled by default)

```
<table class="govuk-table enhanced-table data-size-to-fit">
  <thead class="govuk-table__head">
    <tr class="govuk-table__row">
      <th class="govuk-table__header" data-sortable data-renderer="htmlRenderer">A link</th>
      <th class="govuk-table__header" data-sortable data-renderer="dateRenderer">A date</th>
      <th class="govuk-table__header" data-width="300">Some text</th>
      <th class="govuk-table__header" data-column-type="numericColumn">A number</th>
  </thead>
  <tbody class="govuk-table__body">
    {% for object in object_list %}
      <tr>
        <td class="name govuk-table__cell">
          <a class="govuk-link" href="#">The link</a>
        </td>
        ...
      </tr>
    {% endfor %}
  </tbody>
</table>
```

## Initialise it

Add the following to your page

```
<script src="{% static 'ag-grid-community.min.js' %}"></script>
<script src="{% static 'dayjs.min.js' %}"></script>
<script src="{% static 'js/grid-utils.js' %}"></script>
<script src="{% static 'js/enhanced-table.js' %}"></script>
<link rel="stylesheet" type="text/css" href="{% static 'data-grid.css' %}"/>
<script nonce="{{ request.csp_nonce }}">
  document.addEventListener('DOMContentLoaded', () => {
    initEnhancedTable("enhanced-table");
  });
</script>
```
