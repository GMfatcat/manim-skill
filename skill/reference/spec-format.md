# Scene Spec Format

A scene spec is a JSON object describing one animation clip. It has a `title`, an optional `aspect_ratio` (default `16:9`), and a non-empty list of `beats`. Each beat names a `component` (see the component reference) or `raw` with a `code` field of manim Python where the scene is `self`.

## SceneSpec schema

```json
{
  "$defs": {
    "Beat": {
      "properties": {
        "component": {
          "title": "Component",
          "type": "string"
        },
        "params": {
          "additionalProperties": true,
          "title": "Params",
          "type": "object"
        },
        "code": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Code"
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
        },
        "duration": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Duration"
        },
        "camera": {
          "anyOf": [
            {
              "$ref": "#/$defs/CameraDirective"
            },
            {
              "type": "null"
            }
          ],
          "default": null
        }
      },
      "required": [
        "component"
      ],
      "title": "Beat",
      "type": "object"
    },
    "CameraDirective": {
      "properties": {
        "action": {
          "enum": [
            "focus",
            "zoom",
            "pan",
            "reset"
          ],
          "title": "Action",
          "type": "string"
        },
        "target": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Target"
        },
        "scale": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Scale"
        }
      },
      "required": [
        "action"
      ],
      "title": "CameraDirective",
      "type": "object"
    }
  },
  "properties": {
    "title": {
      "title": "Title",
      "type": "string"
    },
    "aspect_ratio": {
      "default": "16:9",
      "enum": [
        "16:9",
        "1:1",
        "9:16"
      ],
      "title": "Aspect Ratio",
      "type": "string"
    },
    "beats": {
      "items": {
        "$ref": "#/$defs/Beat"
      },
      "minItems": 1,
      "title": "Beats",
      "type": "array"
    }
  },
  "required": [
    "title",
    "beats"
  ],
  "title": "SceneSpec",
  "type": "object"
}
```

## Beat schema

```json
{
  "$defs": {
    "CameraDirective": {
      "properties": {
        "action": {
          "enum": [
            "focus",
            "zoom",
            "pan",
            "reset"
          ],
          "title": "Action",
          "type": "string"
        },
        "target": {
          "anyOf": [
            {
              "type": "string"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Target"
        },
        "scale": {
          "anyOf": [
            {
              "type": "number"
            },
            {
              "type": "null"
            }
          ],
          "default": null,
          "title": "Scale"
        }
      },
      "required": [
        "action"
      ],
      "title": "CameraDirective",
      "type": "object"
    }
  },
  "properties": {
    "component": {
      "title": "Component",
      "type": "string"
    },
    "params": {
      "additionalProperties": true,
      "title": "Params",
      "type": "object"
    },
    "code": {
      "anyOf": [
        {
          "type": "string"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Code"
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
    },
    "duration": {
      "anyOf": [
        {
          "type": "number"
        },
        {
          "type": "null"
        }
      ],
      "default": null,
      "title": "Duration"
    },
    "camera": {
      "anyOf": [
        {
          "$ref": "#/$defs/CameraDirective"
        },
        {
          "type": "null"
        }
      ],
      "default": null
    }
  },
  "required": [
    "component"
  ],
  "title": "Beat",
  "type": "object"
}
```

## Example

```json
{
  "title": "Self-Attention",
  "aspect_ratio": "16:9",
  "beats": [
    {
      "component": "TextBeat",
      "params": {
        "text": "Self-Attention",
        "style": "title"
      },
      "caption": "Intro",
      "duration": 2.0
    },
    {
      "component": "raw",
      "code": "c = Circle()\nself.play(Create(c))",
      "duration": 3.0
    }
  ]
}
```
