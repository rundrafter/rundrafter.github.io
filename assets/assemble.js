function omitEmpty(obj) {
  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    result[key] = value;
  }
  return result;
}

function omitEmptyPreferredSessions(weeklySchedule) {
  if (!Array.isArray(weeklySchedule.preferred_sessions)) return weeklySchedule;
  return {
    ...weeklySchedule,
    preferred_sessions: weeklySchedule.preferred_sessions.map(omitEmpty),
  };
}

// Whether a value carries user-entered content, for deciding if a whole
// optional section/row was left blank and should be omitted rather than
// emitted as an empty or partial object.
function hasContent(value) {
  if (value === undefined || value === null || value === "" || value === false) {
    return false;
  }
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.values(value).some(hasContent);
  return true;
}

// Prunes an optional object-shaped section: undefined if the runner left it
// blank, otherwise the section with its own empty fields dropped.
function pruneOptionalObject(obj) {
  if (!obj || !hasContent(obj)) return undefined;
  return omitEmpty(obj);
}

function pruneStrengthCross(strengthCross) {
  const cleaned = pruneOptionalObject(strengthCross);
  if (!cleaned) return undefined;
  const crossTraining = pruneOptionalObject(cleaned.cross_training);
  if (crossTraining) cleaned.cross_training = crossTraining;
  else delete cleaned.cross_training;
  return cleaned;
}

// Prunes a repeating optional section (injuries, b_races, other_events):
// drops blank rows, then omits the whole array if nothing is left.
function pruneRepeatingSection(rows) {
  if (!Array.isArray(rows)) return undefined;
  const kept = rows.filter(hasContent).map(omitEmpty);
  return kept.length > 0 ? kept : undefined;
}

// Cross-field product rules the schema can't express (see docs/spec/webform.md).
// Returns human-readable messages; an empty array means the rules all pass.
function validateCrossField(formState) {
  const errors = [];
  const goal = formState.goal ?? {};
  const consent = formState.consent ?? {};
  const healthScreen = formState.health_screen ?? {};
  const output = formState.output ?? {};

  if (consent.disclaimer_accepted !== true) {
    errors.push("You must accept the disclaimer to continue.");
  }

  const healthFlagRaised = Object.entries(healthScreen).some(
    ([key, value]) => key !== "other_reason" && value === true,
  );
  if (healthFlagRaised && consent.health_acknowledged !== true) {
    errors.push(
      "Please acknowledge the medical-clearance guidance before continuing.",
    );
  }

  if (goal.start_date && goal.date && goal.start_date > goal.date) {
    errors.push("Plan start date must be on or before the race date.");
  }

  for (const race of formState.b_races ?? []) {
    if (race?.date && goal.date && race.date >= goal.date) {
      errors.push(
        `B race "${race.name || race.date}" date must be before the goal race date.`,
      );
    }
  }

  for (const event of formState.other_events ?? []) {
    if (event?.date && goal.date && event.date >= goal.date) {
      errors.push(
        `Other event "${event.name || event.date}" date must be before the goal race date.`,
      );
    }
  }

  if (!Array.isArray(output.formats) || output.formats.length === 0) {
    errors.push("Select at least one output format.");
  }

  return errors;
}

export function assemble(formState, { now } = {}) {
  const timestamp = now ?? new Date().toISOString();
  const errors = validateCrossField(formState);

  const runner = pruneOptionalObject(formState.runner);
  const strengthCross = pruneStrengthCross(formState.strength_cross);
  const injuries = pruneRepeatingSection(formState.injuries);
  const bRaces = pruneRepeatingSection(formState.b_races);
  const otherEvents = pruneRepeatingSection(formState.other_events);
  const notes = pruneOptionalObject(formState.notes);

  const intake = {
    meta: { schema_version: "1", submitted_at: timestamp },
    units: formState.units,
    ...(runner && { runner }),
    goal: omitEmpty(formState.goal ?? {}),
    recent_result: omitEmpty(formState.recent_result ?? {}),
    current_fitness: omitEmpty(formState.current_fitness ?? {}),
    weekly_schedule: omitEmptyPreferredSessions(
      omitEmpty(formState.weekly_schedule ?? {}),
    ),
    ...(strengthCross && { strength_cross: strengthCross }),
    preferences: omitEmpty(formState.preferences ?? {}),
    ...(injuries && { injuries }),
    health_screen: omitEmpty(formState.health_screen ?? {}),
    consent: omitEmpty({
      ...formState.consent,
      accepted_at: timestamp,
    }),
    ...(bRaces && { b_races: bRaces }),
    ...(otherEvents && { other_events: otherEvents }),
    ...(notes && { notes }),
    output: omitEmpty(formState.output ?? {}),
  };

  return { intake, errors };
}
