export default {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RunDrafter intake",
  "description": "Raw intake from the web form (stage 0 output).",
  "type": "object",
  "required": [
    "meta",
    "units",
    "runner",
    "goal"
  ],
  "additionalProperties": false,
  "$defs": {
    "half_day_availability": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "morning": {
          "type": "boolean"
        },
        "evening": {
          "type": "boolean"
        }
      }
    },
    "broad_session_type": {
      "type": "string",
      "enum": [
        "easy",
        "quality",
        "recovery",
        "long",
        "strength",
        "cross_training"
      ]
    }
  },
  "properties": {
    "meta": {
      "type": "object",
      "required": [
        "schema_version",
        "submitted_at"
      ],
      "additionalProperties": false,
      "properties": {
        "schema_version": {
          "type": "string",
          "const": "2"
        },
        "submitted_at": {
          "type": "string"
        }
      }
    },
    "units": {
      "type": "string",
      "enum": [
        "km",
        "mi"
      ]
    },
    "runner": {
      "type": "object",
      "required": [
        "experience"
      ],
      "additionalProperties": false,
      "properties": {
        "name": {
          "type": "string",
          "minLength": 1
        },
        "experience": {
          "type": "string",
          "enum": [
            "new",
            "returning",
            "experienced"
          ]
        }
      }
    },
    "goal": {
      "type": "object",
      "required": [
        "race",
        "distance",
        "date",
        "target_time",
        "start_date"
      ],
      "additionalProperties": false,
      "properties": {
        "race": {
          "type": "string"
        },
        "distance": {
          "type": "string",
          "enum": [
            "5k",
            "10k",
            "half",
            "marathon"
          ]
        },
        "date": {
          "type": "string",
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
        },
        "target_time": {
          "type": "string",
          "pattern": "^([0-9]+:[0-5][0-9]:[0-5][0-9]|[0-9]+:[0-5][0-9]|finish|suggest)$"
        },
        "start_date": {
          "type": "string",
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
        }
      }
    },
    "recent_result": {
      "type": "object",
      "required": [
        "distance",
        "time",
        "date"
      ],
      "additionalProperties": false,
      "properties": {
        "distance": {
          "type": "string",
          "enum": [
            "5k",
            "10k",
            "half",
            "marathon"
          ]
        },
        "time": {
          "type": "string",
          "pattern": "^[0-9]+:[0-5][0-9](:[0-5][0-9])?$"
        },
        "date": {
          "type": "string",
          "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
        }
      }
    },
    "current_fitness": {
      "type": "object",
      "required": [
        "weekly_distance",
        "longest_run"
      ],
      "additionalProperties": false,
      "properties": {
        "weekly_distance": {
          "type": "number",
          "minimum": 0
        },
        "longest_run": {
          "type": "number",
          "minimum": 0
        },
        "recent_peak_weekly": {
          "type": "number",
          "exclusiveMinimum": 0
        },
        "vdot": {
          "type": "number",
          "exclusiveMinimum": 0,
          "description": "Computed by the form from recent_result. Authoritative for stage 2; stage 1 recomputes it from recent_result and rejects a mismatch beyond tolerance."
        }
      }
    },
    "weekly_schedule": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "availability": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "Monday": {
              "$ref": "#/$defs/half_day_availability"
            },
            "Tuesday": {
              "$ref": "#/$defs/half_day_availability"
            },
            "Wednesday": {
              "$ref": "#/$defs/half_day_availability"
            },
            "Thursday": {
              "$ref": "#/$defs/half_day_availability"
            },
            "Friday": {
              "$ref": "#/$defs/half_day_availability"
            },
            "Saturday": {
              "$ref": "#/$defs/half_day_availability"
            },
            "Sunday": {
              "$ref": "#/$defs/half_day_availability"
            }
          }
        },
        "preferred_sessions": {
          "type": "array",
          "items": {
            "type": "object",
            "required": [
              "day",
              "type"
            ],
            "additionalProperties": false,
            "properties": {
              "day": {
                "type": "string",
                "enum": [
                  "Monday",
                  "Tuesday",
                  "Wednesday",
                  "Thursday",
                  "Friday",
                  "Saturday",
                  "Sunday"
                ]
              },
              "type": {
                "description": "One broad type, or two or more distinct types meaning any of these - whichever fits the week best.",
                "oneOf": [
                  {
                    "$ref": "#/$defs/broad_session_type"
                  },
                  {
                    "type": "array",
                    "items": {
                      "$ref": "#/$defs/broad_session_type"
                    },
                    "minItems": 2,
                    "uniqueItems": true
                  }
                ]
              },
              "description": {
                "type": "string"
              },
              "distance_min": {
                "type": "number",
                "minimum": 0
              },
              "distance_max": {
                "type": "number",
                "minimum": 0
              },
              "tailored": {
                "type": "boolean",
                "default": true
              },
              "time_of_day": {
                "type": "string",
                "enum": [
                  "morning",
                  "evening"
                ]
              }
            }
          }
        }
      }
    },
    "progress": {
      "type": "object",
      "additionalProperties": true,
      "properties": {
        "as_of_date": {
          "type": "string"
        },
        "completed": {
          "type": "object"
        },
        "new_recent_result": {
          "type": "object"
        },
        "changes": {
          "type": "object"
        }
      }
    },
    "b_races": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "name",
          "distance",
          "date",
          "target_time"
        ],
        "additionalProperties": false,
        "properties": {
          "name": {
            "type": "string"
          },
          "distance": {
            "type": "string",
            "enum": [
              "5k",
              "10k",
              "half",
              "marathon"
            ]
          },
          "date": {
            "type": "string",
            "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
          },
          "target_time": {
            "description": "No 'suggest' sentinel here - calibration projects a target only for the goal, not a B race.",
            "type": "string",
            "pattern": "^([0-9]+:[0-5][0-9]:[0-5][0-9]|[0-9]+:[0-5][0-9]|finish)$"
          }
        }
      }
    },
    "other_events": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "date",
          "type"
        ],
        "additionalProperties": false,
        "properties": {
          "date": {
            "type": "string",
            "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$"
          },
          "type": {
            "description": "One broad type, or two or more distinct types meaning the runner would accept any of these for this event - chosen once, for its single date.",
            "oneOf": [
              {
                "$ref": "#/$defs/broad_session_type"
              },
              {
                "type": "array",
                "items": {
                  "$ref": "#/$defs/broad_session_type"
                },
                "minItems": 2,
                "uniqueItems": true
              }
            ]
          },
          "description": {
            "type": "string"
          },
          "distance_min": {
            "type": "number",
            "minimum": 0
          },
          "distance_max": {
            "type": "number",
            "minimum": 0
          }
        }
      }
    },
    "notes": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "other": {
          "type": "string"
        }
      }
    },
    "output": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "quality_detail": {
          "description": "Whether quality sessions carry prescribed pace/workout detail ('specific', the default) or only type, description and distance ('generic'). Applies to every quality session, not just weekly-template entries.",
          "type": "string",
          "enum": [
            "specific",
            "generic"
          ],
          "default": "specific"
        }
      }
    }
  }
};
