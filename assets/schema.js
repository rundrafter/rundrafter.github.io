export default {
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "RunDrafter intake",
  "description": "Raw intake from the web form (stage 0 output).",
  "type": "object",
  "required": [
    "meta",
    "units",
    "runner",
    "goal",
    "recent_result",
    "current_fitness",
    "health_screen",
    "consent"
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
          "const": "1"
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
        "name",
        "experience"
      ],
      "additionalProperties": false,
      "properties": {
        "name": {
          "type": "string",
          "minLength": 1
        },
        "age": {
          "type": "integer",
          "minimum": 0
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
          "pattern": "^([0-9]+:[0-5][0-9]:[0-5][0-9]|[0-9]+:[0-5][0-9]|finish)$"
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
          "exclusiveMinimum": 0
        },
        "longest_run": {
          "type": "number",
          "exclusiveMinimum": 0
        },
        "recent_peak_weekly": {
          "type": "number",
          "exclusiveMinimum": 0
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
        "long_run_day": {
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
        "rest_days": {
          "type": "array",
          "items": {
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
          "minItems": 1
        },
        "preferred_sessions": {
          "type": "array",
          "items": {
            "type": "object",
            "required": [
              "day",
              "description"
            ],
            "additionalProperties": false,
            "dependentRequired": {
              "distance": [
                "effort"
              ],
              "effort": [
                "distance"
              ]
            },
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
              "description": {
                "type": "string"
              },
              "distance": {
                "type": "number",
                "exclusiveMinimum": 0
              },
              "effort": {
                "type": "string",
                "enum": [
                  "easy",
                  "threshold"
                ]
              }
            }
          }
        }
      }
    },
    "strength_cross": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "strength_per_week": {
          "type": "integer",
          "minimum": 0
        },
        "strength_days": {
          "type": "array",
          "items": {
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
          }
        },
        "strength_type": {
          "type": "string"
        },
        "warmup_jog": {
          "type": "boolean"
        },
        "cross_training": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "type": {
              "type": "string"
            },
            "frequency": {
              "type": "string"
            }
          }
        }
      }
    },
    "preferences": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "calibrate_to": {
          "type": "string",
          "enum": [
            "current",
            "goal"
          ]
        },
        "build_mode": {
          "type": "string",
          "enum": [
            "cautious",
            "standard"
          ]
        }
      }
    },
    "injuries": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "area",
          "status"
        ],
        "additionalProperties": false,
        "properties": {
          "area": {
            "type": "string"
          },
          "status": {
            "type": "string",
            "enum": [
              "current",
              "recent",
              "historical"
            ]
          },
          "notes": {
            "type": "string"
          }
        }
      }
    },
    "health_screen": {
      "type": "object",
      "required": [
        "heart_condition",
        "chest_pain_activity",
        "chest_pain_rest",
        "dizziness_balance",
        "bone_joint_problem",
        "bp_or_heart_meds",
        "pregnancy",
        "recent_surgery_illness"
      ],
      "additionalProperties": false,
      "properties": {
        "heart_condition": {
          "type": "boolean"
        },
        "chest_pain_activity": {
          "type": "boolean"
        },
        "chest_pain_rest": {
          "type": "boolean"
        },
        "dizziness_balance": {
          "type": "boolean"
        },
        "bone_joint_problem": {
          "type": "boolean"
        },
        "bp_or_heart_meds": {
          "type": "boolean"
        },
        "pregnancy": {
          "type": "boolean"
        },
        "recent_surgery_illness": {
          "type": "boolean"
        },
        "other_reason": {
          "type": "string"
        }
      }
    },
    "consent": {
      "type": "object",
      "required": [
        "disclaimer_accepted"
      ],
      "additionalProperties": false,
      "properties": {
        "disclaimer_accepted": {
          "type": "boolean"
        },
        "terms_accepted": {
          "type": "boolean"
        },
        "health_acknowledged": {
          "type": "boolean"
        },
        "accepted_at": {
          "type": "string"
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
          "date"
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
            "type": "string"
          }
        }
      }
    },
    "other_events": {
      "type": "array",
      "items": {
        "type": "object",
        "required": [
          "name",
          "distance",
          "date"
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
        "formats": {
          "type": "array",
          "items": {
            "type": "string",
            "enum": [
              "spreadsheet",
              "pdf"
            ]
          },
          "minItems": 1,
          "uniqueItems": true
        }
      }
    }
  }
};
