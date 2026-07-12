const DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

// A day whose grid has both halves unticked is never a running day (mirrors
// resolve.py's _both_halves_unticked); an absent day or half defaults to
// available, matching the schema default.
function isDayFullyUnavailable(availability, day) {
  const halves = availability?.[day] ?? {};
  return halves.morning === false && halves.evening === false;
}

function omitEmpty(obj) {
  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value) && value.length === 0) continue;
    result[key] = value;
  }
  return result;
}

// Maps one weekly-session-template row from its form shape (a
// `skip_tailoring` tickbox) to the contract shape (ADR 014): `tailored` is
// omitted when true (the schema default) and only emitted as `false` when
// the tickbox was checked.
function mapPreferredSession(session) {
  const { skip_tailoring, ...rest } = session ?? {};
  return omitEmpty({ ...rest, ...(skip_tailoring ? { tailored: false } : {}) });
}

function mapPreferredSessions(weeklySchedule) {
  if (!Array.isArray(weeklySchedule.preferred_sessions)) return weeklySchedule;
  return {
    ...weeklySchedule,
    preferred_sessions: weeklySchedule.preferred_sessions.map(mapPreferredSession),
  };
}

// Sparsifies the availability grid: absent = available (the schema
// default), so only an explicitly unticked half-day is worth emitting. A
// weekday with nothing unticked is dropped entirely.
function pruneAvailability(availability) {
  if (!availability) return undefined;
  const sparse = {};
  for (const [day, halves] of Object.entries(availability)) {
    const unticked = {};
    if (halves?.morning === false) unticked.morning = false;
    if (halves?.evening === false) unticked.evening = false;
    if (Object.keys(unticked).length > 0) sparse[day] = unticked;
  }
  return Object.keys(sparse).length > 0 ? sparse : undefined;
}

// Prunes weekly_schedule to an override-only object: the availability grid
// keeps only unticked half-days, long_run_day/preferred_sessions drop when
// left on "let RunDrafter decide", and the whole section is omitted when
// nothing was overridden. There is no `rest_days` override any more (ADR
// 017) - the resolver always derives rest days.
function pruneWeeklySchedule(schedule) {
  if (!schedule) return undefined;
  const { availability, ...rest } = mapPreferredSessions(omitEmpty(schedule));
  const sparseAvailability = pruneAvailability(availability);
  const cleaned = sparseAvailability ? { ...rest, availability: sparseAvailability } : rest;
  return Object.keys(cleaned).length > 0 ? cleaned : undefined;
}

// Resolves the goal's target-time radio (form-only field, never part of the
// contract) into the schema's three-way `target_time`: the entered specific
// time, or the "finish"/"suggest" literal (ADR 016).
function resolveGoal(goal) {
  const { target_time_mode, ...rest } = goal ?? {};
  const target_time =
    target_time_mode === "finish" || target_time_mode === "suggest"
      ? target_time_mode
      : rest.target_time;
  return omitEmpty({ ...rest, target_time });
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

// Prunes a repeating optional section (b_races, other_events): drops blank
// rows, then omits the whole array if nothing is left.
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

// Days whose grid has both halves unticked (see isDayFullyUnavailable) - never
// a running day, regardless of what the resolver later decides.
function getUnavailableDays(schedule) {
  const availability = schedule.availability ?? {};
  return DAY_NAMES.filter((day) => isDayFullyUnavailable(availability, day));
}

// A day the grid marks fully-unticked is never a running day, so 5 or more of
// them out of 7 already leaves at most 2 possibly-trainable days - guaranteed
// under the resolver's 3-day minimum (SCHEDULE_UNDER_CONSTRAINED in
// validate.py) no matter which rest days it picks. This is the one case of
// that resolver-side warning the grid can express without running the
// resolver; a looser grid may still end up under-constrained once the
// resolver adds rest days, but that isn't form-checkable.
const MIN_TRAINABLE_DAYS = 3;

// Cross-field product rules the schema can't express (see docs/architecture.md).
// Mirrors rundrafter's stage 1 (validate.py / contracts.md) rule-for-rule.
// Returns human-readable messages; an empty array means the rules all pass.
function validateCrossField(formState) {
  const errors = [];
  const goal = formState.goal ?? {};
  const recentResult = formState.recent_result ?? {};
  const schedule = formState.weekly_schedule ?? {};

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

  // b_races name themselves; other_events have no name field, so they're
  // labelled by type instead (mirrors validate.py's _validate_date_ordering).
  const events = [
    ...(formState.b_races ?? []).map((row) => ({
      label: "B race",
      name: row?.name,
      row,
    })),
    ...(formState.other_events ?? []).map((row) => ({
      label: "Other event",
      name: row?.type,
      row,
    })),
  ];

  const seenDates = new Map();
  for (const { label, name, row } of events) {
    if (!row?.date) continue;
    const eventLabel = `${label} "${name || row.date}"`;

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

  // days_available and rest_days are no longer raw-intake fields (ADR 017 -
  // the resolver always derives them from the availability grid +
  // runner.experience) and long_run_day is an optional override, so an
  // unset grid/override is "let RunDrafter decide", not a validation
  // failure. A preferred session landing on a resolver-derived rest day can
  // only be caught once the resolver has run (validate.py's
  // _validate_resolved_schedule), which this form can't do; an
  // under-constrained grid is generally a resolver-side warning
  // (SCHEDULE_UNDER_CONSTRAINED) this form can't check either - except the
  // 5-or-more-unticked-days case handled as a warning below, which is
  // guaranteed regardless of what the resolver decides. Individual
  // never-available days (both halves unticked), though, the grid can
  // express directly, so overrides are checked against those below.
  const unavailableDays = getUnavailableDays(schedule);

  if (schedule.long_run_day && unavailableDays.includes(schedule.long_run_day)) {
    errors.push(
      `Long run day (${schedule.long_run_day}) has both halves unticked in the availability grid.`,
    );
  }

  const preferredOnUnavailableDay = [
    ...new Set(
      (schedule.preferred_sessions ?? [])
        .map((session) => session?.day)
        .filter((day) => day && unavailableDays.includes(day)),
    ),
  ];
  if (preferredOnUnavailableDay.length > 0) {
    errors.push(
      `Preferred session day(s) ${preferredOnUnavailableDay.join(", ")} have both halves unticked in the availability grid.`,
    );
  }

  errors.push(
    ...validateSessionRanges(schedule.preferred_sessions, "Weekly session"),
  );
  errors.push(...validateSessionRanges(formState.other_events, "Other event"));

  return errors;
}

// Mirrors validate.py's _validate_session_ranges: distance_max must be >=
// distance_min when both are given, on both preferred_sessions and
// other_events rows.
function validateSessionRanges(entries, label) {
  const errors = [];
  for (const entry of entries ?? []) {
    const min = entry?.distance_min;
    const max = entry?.distance_max;
    if (min === undefined || min === null || max === undefined || max === null) {
      continue;
    }
    if (max < min) {
      const rowLabel = entry.description || entry.day || entry.date || "session";
      errors.push(
        `${label} "${rowLabel}": maximum distance (${max}) must be >= minimum distance (${min}).`,
      );
    }
  }
  return errors;
}

// Non-blocking advisories (see docs/architecture.md's "Non-blocking" rules).
function validateWarnings(formState) {
  const warnings = [];
  const goal = formState.goal ?? {};
  const recentResult = formState.recent_result ?? {};
  const schedule = formState.weekly_schedule ?? {};

  if (
    recentResult.date &&
    goal.start_date &&
    daysBetween(goal.start_date, recentResult.date) > 183
  ) {
    warnings.push(
      "Recent result date is more than 6 months before the plan start date — VDOT-derived paces may not reflect current fitness.",
    );
  }

  const unavailableDayCount = getUnavailableDays(schedule).length;
  if (DAY_NAMES.length - unavailableDayCount < MIN_TRAINABLE_DAYS) {
    warnings.push(
      `The availability grid leaves both halves unticked on ${unavailableDayCount} day(s) — at most ${DAY_NAMES.length - unavailableDayCount} day(s) a week can ever be trainable, short of the ${MIN_TRAINABLE_DAYS} recommended for a sane training week.`,
    );
  }

  return warnings;
}

export function assemble(formState, { now } = {}) {
  const timestamp = now ?? new Date().toISOString();
  const errors = validateCrossField(formState);
  const warnings = validateWarnings(formState);

  const bRaces = pruneRepeatingSection(formState.b_races);
  const otherEvents = pruneRepeatingSection(formState.other_events);
  const notes = pruneOptionalObject(formState.notes);
  const weeklySchedule = pruneWeeklySchedule(formState.weekly_schedule);
  const recentResult = pruneOptionalObject(formState.recent_result);
  const currentFitness = pruneOptionalObject(formState.current_fitness);

  const intake = {
    meta: { schema_version: "1", submitted_at: timestamp },
    units: formState.units,
    runner: omitEmpty(formState.runner ?? {}),
    goal: resolveGoal(formState.goal),
    ...(currentFitness && { current_fitness: currentFitness }),
    ...(recentResult && { recent_result: recentResult }),
    ...(weeklySchedule && { weekly_schedule: weeklySchedule }),
    ...(bRaces && { b_races: bRaces }),
    ...(otherEvents && { other_events: otherEvents }),
    ...(notes && { notes }),
  };

  return { intake, errors, warnings };
}
