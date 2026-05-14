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
