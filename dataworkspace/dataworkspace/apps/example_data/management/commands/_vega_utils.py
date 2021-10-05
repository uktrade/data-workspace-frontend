import random


def get_fake_vega_definition():
    definitions = get_definitions()

    offset = random.randint(0, len(definitions) - 1)

    return definitions[offset]


def get_definitions():
    definitions = []

    definitions.append(
        """
    {
  "$schema": "https://vega.github.io/schema/vega/v5.json",
  "description": "A basic line chart example.",
  "width": 500,
  "height": 200,
  "padding": 5,

  "signals": [
    {
      "name": "interpolate",
      "value": "linear",
      "bind": {
        "input": "select",
        "options": [
          "basis",
          "cardinal",
          "catmull-rom",
          "linear",
          "monotone",
          "natural",
          "step",
          "step-after",
          "step-before"
        ]
      }
    }
  ],

  "data": [
    {
      "name": "table",
      "values": [
        {"x": 0, "y": 28, "c":0}, {"x": 0, "y": 20, "c":1},
        {"x": 1, "y": 43, "c":0}, {"x": 1, "y": 35, "c":1},
        {"x": 2, "y": 81, "c":0}, {"x": 2, "y": 10, "c":1},
        {"x": 3, "y": 19, "c":0}, {"x": 3, "y": 15, "c":1},
        {"x": 4, "y": 52, "c":0}, {"x": 4, "y": 48, "c":1},
        {"x": 5, "y": 24, "c":0}, {"x": 5, "y": 28, "c":1},
        {"x": 6, "y": 87, "c":0}, {"x": 6, "y": 66, "c":1},
        {"x": 7, "y": 17, "c":0}, {"x": 7, "y": 27, "c":1},
        {"x": 8, "y": 68, "c":0}, {"x": 8, "y": 16, "c":1},
        {"x": 9, "y": 49, "c":0}, {"x": 9, "y": 25, "c":1}
      ]
    }
  ],

  "scales": [
    {
      "name": "x",
      "type": "point",
      "range": "width",
      "domain": {"data": "table", "field": "x"}
    },
    {
      "name": "y",
      "type": "linear",
      "range": "height",
      "nice": true,
      "zero": true,
      "domain": {"data": "table", "field": "y"}
    },
    {
      "name": "color",
      "type": "ordinal",
      "range": "category",
      "domain": {"data": "table", "field": "c"}
    }
  ],

  "axes": [
    {"orient": "bottom", "scale": "x"},
    {"orient": "left", "scale": "y"}
  ],

  "marks": [
    {
      "type": "group",
      "from": {
        "facet": {
          "name": "series",
          "data": "table",
          "groupby": "c"
        }
      },
      "marks": [
        {
          "type": "line",
          "from": {"data": "series"},
          "encode": {
            "enter": {
              "x": {"scale": "x", "field": "x"},
              "y": {"scale": "y", "field": "y"},
              "stroke": {"scale": "color", "field": "c"},
              "strokeWidth": {"value": 2}
            },
            "update": {
              "interpolate": {"signal": "interpolate"},
              "strokeOpacity": {"value": 1}
            },
            "hover": {
              "strokeOpacity": {"value": 0.5}
            }
          }
        }
      ]
    }
  ]
}"""
    )

    definitions.append(
        """
    {
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "description": "A simple pie chart with embedded data.",
  "data": {
    "values": [
      {"category": 1, "value": 4},
      {"category": 2, "value": 6},
      {"category": 3, "value": 10},
      {"category": 4, "value": 3},
      {"category": 5, "value": 7},
      {"category": 6, "value": 8}
    ]
  },
  "mark": "arc",
  "encoding": {
    "theta": {"field": "value", "type": "quantitative"},
    "color": {"field": "category", "type": "nominal"}
  },
  "view": {"stroke": null}
}
    """
    )

    definitions.append(
        """
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "description": "A bar graph showing what activites consume what percentage of the day.",
  "data": {
    "values": [
      {"Activity": "Sleeping", "Time": 8},
      {"Activity": "Eating", "Time": 2},
      {"Activity": "TV", "Time": 4},
      {"Activity": "Work", "Time": 8},
      {"Activity": "Exercise", "Time": 2}
    ]
  },
  "transform": [{
    "window": [{
      "op": "sum",
      "field": "Time",
      "as": "TotalTime"
    }],
    "frame": [null, null]
  },
  {
    "calculate": "datum.Time/datum.TotalTime * 100",
    "as": "PercentOfTotal"
  }],
  "height": {"step": 12},
  "mark": "bar",
  "encoding": {
    "x": {
      "field": "PercentOfTotal",
      "type": "quantitative",
      "title": "% of total Time"
    },
    "y": {"field": "Activity", "type": "nominal"}
  }
}
    """
    )

    definitions.append(
        """
{
  "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
  "description": "A simple donut chart with embedded data.",
  "data": {
    "values": [
      {"category": 1, "value": 4},
      {"category": 2, "value": 6},
      {"category": 3, "value": 10},
      {"category": 4, "value": 3},
      {"category": 5, "value": 7},
      {"category": 6, "value": 8}
    ]
  },
  "mark": {"type": "arc", "innerRadius": 50},
  "encoding": {
    "theta": {"field": "value", "type": "quantitative"},
    "color": {"field": "category", "type": "nominal"}
  }
}
    """
    )

    return definitions
