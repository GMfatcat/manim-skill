# Component Reference

Each component below can be used as a beat's `component` in a scene spec. A beat's `params` must match the component's params schema.

### AttentionFlow
{
  "properties": {
    "tokens": {
      "items": {
        "type": "string"
      },
      "minItems": 1,
      "title": "Tokens",
      "type": "array"
    },
    "highlight": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Highlight"
    },
    "weights": {
      "items": {
        "type": "number"
      },
      "title": "Weights",
      "type": "array"
    }
  },
  "required": [
    "tokens"
  ],
  "title": "AttentionFlowParams",
  "type": "object"
}

### CodeWalkthrough
{
  "properties": {
    "code": {
      "title": "Code",
      "type": "string"
    },
    "language": {
      "default": "python",
      "title": "Language",
      "type": "string"
    },
    "highlight_lines": {
      "items": {
        "items": {
          "type": "integer"
        },
        "type": "array"
      },
      "title": "Highlight Lines",
      "type": "array"
    }
  },
  "required": [
    "code"
  ],
  "title": "CodeWalkthroughParams",
  "type": "object"
}

### FormulaBreakdown
{
  "properties": {
    "formula": {
      "title": "Formula",
      "type": "string"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "formula"
  ],
  "title": "FormulaBreakdownParams",
  "type": "object"
}

### FormulaWalkthrough
{
  "$defs": {
    "FormulaStep": {
      "properties": {
        "indices": {
          "items": {
            "type": "integer"
          },
          "minItems": 1,
          "title": "Indices",
          "type": "array"
        },
        "caption": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Caption"
        }
      },
      "required": [
        "indices"
      ],
      "title": "FormulaStep",
      "type": "object"
    }
  },
  "properties": {
    "segments": {
      "items": {
        "type": "string"
      },
      "minItems": 1,
      "title": "Segments",
      "type": "array"
    },
    "steps": {
      "items": {
        "$ref": "#/$defs/FormulaStep"
      },
      "title": "Steps",
      "type": "array"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "segments"
  ],
  "title": "FormulaWalkthroughParams",
  "type": "object"
}

### FunctionPlot
{
  "properties": {
    "expression": {
      "title": "Expression",
      "type": "string"
    },
    "x_range": {
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 2,
      "title": "X Range",
      "type": "array"
    },
    "y_range": {
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 2,
      "title": "Y Range",
      "type": "array"
    },
    "x_label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "X Label"
    },
    "y_label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Y Label"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "expression"
  ],
  "title": "FunctionPlotParams",
  "type": "object"
}

### GeometryAnim
{
  "properties": {
    "shape": {
      "default": "circle",
      "enum": [
        "circle",
        "square",
        "triangle",
        "polygon"
      ],
      "title": "Shape",
      "type": "string"
    },
    "transform": {
      "default": "none",
      "enum": [
        "rotate",
        "scale",
        "none"
      ],
      "title": "Transform",
      "type": "string"
    },
    "label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Label"
    }
  },
  "title": "GeometryAnimParams",
  "type": "object"
}

### GraphBeat
{
  "properties": {
    "nodes": {
      "items": {
        "type": "string"
      },
      "minItems": 1,
      "title": "Nodes",
      "type": "array"
    },
    "edges": {
      "items": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "title": "Edges",
      "type": "array"
    },
    "directed": {
      "default": false,
      "title": "Directed",
      "type": "boolean"
    },
    "layout": {
      "default": "spring",
      "enum": [
        "spring",
        "circular",
        "tree",
        "kamada_kawai",
        "planar"
      ],
      "title": "Layout",
      "type": "string"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "nodes"
  ],
  "title": "GraphBeatParams",
  "type": "object"
}

### HeatmapBeat
{
  "properties": {
    "values": {
      "items": {
        "items": {
          "type": "number"
        },
        "type": "array"
      },
      "minItems": 1,
      "title": "Values",
      "type": "array"
    },
    "row_labels": {
      "items": {
        "type": "string"
      },
      "title": "Row Labels",
      "type": "array"
    },
    "col_labels": {
      "items": {
        "type": "string"
      },
      "title": "Col Labels",
      "type": "array"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    },
    "low_color": {
      "default": "#34597A",
      "title": "Low Color",
      "type": "string"
    },
    "high_color": {
      "default": "#9A3B2E",
      "title": "High Color",
      "type": "string"
    }
  },
  "required": [
    "values"
  ],
  "title": "HeatmapBeatParams",
  "type": "object"
}

### MatrixOp
{
  "properties": {
    "op": {
      "default": "matmul",
      "enum": [
        "matmul",
        "transpose",
        "reshape"
      ],
      "title": "Op",
      "type": "string"
    },
    "a_label": {
      "default": "A",
      "title": "A Label",
      "type": "string"
    },
    "b_label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "B Label"
    },
    "result_label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Result Label"
    }
  },
  "title": "MatrixOpParams",
  "type": "object"
}

### NeuralNetDiagram
{
  "properties": {
    "layers": {
      "items": {
        "type": "integer"
      },
      "minItems": 1,
      "title": "Layers",
      "type": "array"
    },
    "layer_labels": {
      "items": {
        "type": "string"
      },
      "title": "Layer Labels",
      "type": "array"
    }
  },
  "required": [
    "layers"
  ],
  "title": "NeuralNetDiagramParams",
  "type": "object"
}

### OptimizationPath
{
  "properties": {
    "expression": {
      "title": "Expression",
      "type": "string"
    },
    "x_range": {
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 2,
      "title": "X Range",
      "type": "array"
    },
    "y_range": {
      "items": {
        "type": "number"
      },
      "maxItems": 3,
      "minItems": 2,
      "title": "Y Range",
      "type": "array"
    },
    "start_x": {
      "title": "Start X",
      "type": "number"
    },
    "min_x": {
      "title": "Min X",
      "type": "number"
    },
    "n_steps": {
      "default": 8,
      "minimum": 1,
      "title": "N Steps",
      "type": "integer"
    },
    "x_label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "X Label"
    },
    "y_label": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Y Label"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "expression",
    "x_range",
    "y_range",
    "start_x",
    "min_x"
  ],
  "title": "OptimizationPathParams",
  "type": "object"
}

### PipelineDiagram
{
  "properties": {
    "stages": {
      "items": {
        "type": "string"
      },
      "minItems": 1,
      "title": "Stages",
      "type": "array"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "stages"
  ],
  "title": "PipelineDiagramParams",
  "type": "object"
}

### PlotEvolution
{
  "properties": {
    "series": {
      "items": {
        "type": "number"
      },
      "minItems": 2,
      "title": "Series",
      "type": "array"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    }
  },
  "required": [
    "series"
  ],
  "title": "PlotEvolutionParams",
  "type": "object"
}

### TableBeat
{
  "properties": {
    "headers": {
      "items": {
        "type": "string"
      },
      "minItems": 1,
      "title": "Headers",
      "type": "array"
    },
    "rows": {
      "items": {
        "items": {
          "type": "string"
        },
        "type": "array"
      },
      "minItems": 1,
      "title": "Rows",
      "type": "array"
    },
    "row_labels": {
      "items": {
        "type": "string"
      },
      "title": "Row Labels",
      "type": "array"
    },
    "title": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Title"
    },
    "highlight_cells": {
      "items": {
        "items": {
          "type": "integer"
        },
        "type": "array"
      },
      "title": "Highlight Cells",
      "type": "array"
    }
  },
  "required": [
    "headers",
    "rows"
  ],
  "title": "TableBeatParams",
  "type": "object"
}

### TextBeat
{
  "properties": {
    "text": {
      "title": "Text",
      "type": "string"
    },
    "subtitle": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Subtitle"
    },
    "style": {
      "default": "title",
      "enum": [
        "title",
        "caption",
        "bullets"
      ],
      "title": "Style",
      "type": "string"
    },
    "bullets": {
      "items": {
        "type": "string"
      },
      "title": "Bullets",
      "type": "array"
    }
  },
  "required": [
    "text"
  ],
  "title": "TextBeatParams",
  "type": "object"
}

### (raw-beat theme names)
Available in raw beats: colors PRIMARY, PRIMARY_SOFT, INK, INK_SOFT, INK_FAINT, WARN, HIGHLIGHT, BG, BG_CARD, BG_CODE, RULE; fonts FONT_DISPLAY, FONT_BODY, FONT_MONO; factories title_text, body_text, caption_text, label_text.
