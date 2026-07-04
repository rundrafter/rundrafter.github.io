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

// health_acknowledged is a single checkbox, so an unraised health flag still
// submits it as `false` (omitEmpty keeps booleans); drop it in that case so
// it's only ever present when the runner actually acknowledged the gate.
function pruneConsent(consent, timestamp) {
  const merged = { ...consent, accepted_at: timestamp };
  if (merged.health_acknowledged === false) delete merged.health_acknowledged;
  return omitEmpty(merged);
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

// Day counts between two ISO date strings (a - b), for the >183-day warning
// threshold. Both parse as UTC midnight, so the subtraction is timezone-safe.
function daysBetween(aIso, bIso) {
  return (new Date(aIso) - new Date(bIso)) / 86_400_000;
}

// Cross-field product rules the schema can't express (see docs/architecture.md).
// Mirrors run-drafter's stage 1 (validate.py / contracts.md) rule-for-rule.
// Returns human-readable messages; an empty array means the rules all pass.
function validateCrossField(formState) {
  const errors = [];
  const goal = formState.goal ?? {};
  const consent = formState.consent ?? {};
  const healthScreen = formState.health_screen ?? {};
  const output = formState.output ?? {};
  const recentResult = formState.recent_result ?? {};
  const schedule = formState.weekly_schedule ?? {};

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

  if (goal.start_date && goal.date && goal.start_date >= goal.date) {
    errors.push("Plan start date must be strictly before the goal race date.");
  }

  if (
    recentResult.date &&
    goal.start_date &&
    recentResult.date > goal.start_date
  ) {
    errors.push(
      "Recent result date must be on or before the plan start date.",
    );
  }

  const events = [
    ...(formState.b_races ?? []).map((row) => ({ label: "B race", row })),
    ...(formState.other_events ?? []).map((row) => ({
      label: "Other event",
      row,
    })),
  ];

  const seenDates = new Map();
  for (const { label, row } of events) {
    if (!row?.date) continue;
    const eventLabel = `${label} "${row.name || row.date}"`;

    if (
      goal.start_date &&
      goal.date &&
      !(goal.start_date < row.date && row.date < goal.date)
    ) {
      errors.push(
        `${eventLabel} date must fall strictly between the plan start date and the goal race date.`,
      );
    }

    if (seenDates.has(row.date)) {
      errors.push(
        `${eventLabel} shares a date with ${seenDates.get(row.date)}; each event must be on a unique date.`,
      );
    } else {
      seenDates.set(row.date, eventLabel);
    }
  }

  if (
    schedule.long_run_day &&
    (schedule.rest_days ?? []).includes(schedule.long_run_day)
  ) {
    errors.push("Long run day cannot also be a rest day.");
  }

  if (
    typeof schedule.days_available === "number" &&
    schedule.days_available < 3
  ) {
    errors.push("At least 3 running days per week are required.");
  }

  const restDays = schedule.rest_days ?? [];
  if (restDays.length === 0) {
    errors.push("Select at least one rest day.");
  }

  const preferredOnRestDay = [
    ...new Set(
      (schedule.preferred_sessions ?? [])
        .map((session) => session?.day)
        .filter((day) => day && restDays.includes(day)),
    ),
  ];
  if (preferredOnRestDay.length > 0) {
    errors.push(
      `Preferred session day(s) ${preferredOnRestDay.join(", ")} fall on a rest day.`,
    );
  }

  // Anchor sessions require both distance and effort (dependentRequired in
  // the schema); catch a lopsided pair here with a message naming the row,
  // rather than letting it fall through to a row-index Ajv error.
  for (const session of schedule.preferred_sessions ?? []) {
    const hasDistance = session?.distance !== undefined && session?.distance !== null;
    const hasEffort = session?.effort !== undefined && session?.effort !== null && session?.effort !== "";
    if (hasDistance !== hasEffort) {
      const label = session?.description || session?.day || "session";
      errors.push(
        `Preferred session "${label}" needs both distance and effort to become an anchor session — fill in both or leave both blank.`,
      );
    }
  }

  if (!Array.isArray(output.formats) || output.formats.length === 0) {
    errors.push("Select at least one output format.");
  }

  return errors;
}

// Non-blocking advisories (see docs/architecture.md's "Non-blocking" rules).
function validateWarnings(formState) {
  const warnings = [];
  const goal = formState.goal ?? {};
  const recentResult = formState.recent_result ?? {};

  if (
    recentResult.date &&
    goal.start_date &&
    daysBetween(goal.start_date, recentResult.date) > 183
  ) {
    warnings.push(
      "Recent result date is more than 6 months before the plan start date — VDOT-derived paces may not reflect current fitness.",
    );
  }

  return warnings;
}

export function assemble(formState, { now } = {}) {
  const timestamp = now ?? new Date().toISOString();
  const errors = validateCrossField(formState);
  const warnings = validateWarnings(formState);

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
    consent: pruneConsent(formState.consent, timestamp),
    ...(bRaces && { b_races: bRaces }),
    ...(otherEvents && { other_events: otherEvents }),
    ...(notes && { notes }),
    output: omitEmpty(formState.output ?? {}),
  };

  return { intake, errors, warnings };
}
