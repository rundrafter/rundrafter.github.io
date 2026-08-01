import {
  computeVdot,
  computeVdotFromResult,
  DISTANCE_METRES,
  parseTimeToMinutes,
} from "./vdot.js";
import CONSTRAINTS from "./constraints.js";

const DAY_NAMES = [
  "Monday",
  "Tuesday",
  "Wednesday",
  "Thursday",
  "Friday",
  "Saturday",
  "Sunday",
];

const HALVES = ["morning", "evening"];

// taper_weeks only has marathon/half/shorter entries - 5k and 10k share
// "shorter", mirroring validate.py's _TAPER_KEY_BY_DISTANCE.
const TAPER_KEY_BY_DISTANCE = {
  marathon: "marathon",
  half: "half",
  "5k": "shorter",
  "10k": "shorter",
};

// Mirrors expand/schedule.py's NON_RUNNING_TYPES and SKIP_TAILORABLE_TYPES,
// which the flexible-type rules below are stated in terms of.
const NON_RUNNING_TYPES = new Set(["strength", "cross_training"]);
const SKIP_TAILORABLE_TYPES = new Set([
  "quality",
  "strength",
  "long",
  "cross_training",
]);

// Every broad type an entry offers, whichever form `type` takes - mirrors
// expand/schedule.py's preferred_types. No rule below reads `type` directly.
function preferredTypes(session) {
  const type = session?.type;
  if (Array.isArray(type)) return type;
  return type ? [type] : [];
}

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

// Converts a structured hours/minutes/seconds entry into the H:MM:SS/M:SS
// string the schema's time patterns accept, or undefined when every field
// is blank. Minutes/seconds are zero-padded only when hours are present -
// H:MM:SS requires exactly two digits there, but bare M:SS does not.
function composeStructuredTime({ h, m, s } = {}) {
  if (h === undefined && m === undefined && s === undefined) return undefined;
  const pad = (n) => String(n).padStart(2, "0");
  const minutes = m ?? 0;
  const seconds = pad(s ?? 0);
  return h ? `${h}:${pad(minutes)}:${seconds}` : `${minutes}:${seconds}`;
}

// Converts the tri-state availability grid into the {availability,
// preferred_sessions} shape the rest of this module (and, upstream,
// resolve.py) already works in terms of - see rundrafter's design.md, "The
// availability grid absorbs the session template as a tri-state cell". A
// cell's column supplies its session's time_of_day; that is the only place
// the pin comes from, never a separate control that could contradict it.
function expandGrid(grid) {
  const availability = {};
  const preferredSessions = [];
  for (const day of DAY_NAMES) {
    for (const half of HALVES) {
      const cell = grid?.[day]?.[half];
      const state = cell?.state ?? "available";
      if (state === "unavailable") {
        availability[day] = { ...availability[day], [half]: false };
      } else if (state === "session") {
        preferredSessions.push({
          day,
          time_of_day: half,
          type: cell.type,
          description: cell.description,
          distance_min: cell.distance_min,
          distance_max: cell.distance_max,
          skip_tailoring: cell.skip_tailoring,
        });
      }
    }
  }
  return { availability, preferred_sessions: preferredSessions };
}

// A `type` checkbox group always yields an array; a single ticked type
// collapses to a bare string, since the schema reserves the array form for
// a genuine choice (`minItems: 2`) - one selection has exactly one
// spelling. Shared by preferred_sessions and other_events, both of which
// moved to a checkbox group (ADR 039 / task 9.7). An empty array is left
// alone, falling to `omitEmpty` so the schema's `required` reports the
// missing field.
function collapseSingleType(entry) {
  if (Array.isArray(entry?.type) && entry.type.length === 1) {
    return { ...entry, type: entry.type[0] };
  }
  return entry;
}

// Maps one grid cell's session entry from its form shape (a
// `skip_tailoring` tickbox, plus the type-collapsing above) to the contract
// shape (ADR 014): `tailored` is omitted when true (the schema default) and
// only emitted as `false` when the tickbox was checked.
function mapPreferredSession(session) {
  const { skip_tailoring, ...rest } = collapseSingleType(session) ?? {};
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

// Prunes an expanded weekly_schedule ({availability, preferred_sessions})
// to an override-only object: the availability grid keeps only unticked
// half-days, preferred_sessions drops when the grid never left "available"
// for a session, and the whole section is omitted when nothing was
// overridden. There is no `rest_days` override (ADR 017) - the resolver
// always derives rest days. There is likewise no separate `long_run_day`
// override (ADR 019) - a `type: "long"` preferred_sessions entry is the
// only way to pin the long-run day.
function pruneWeeklySchedule(schedule) {
  if (!schedule) return undefined;
  const { availability, ...rest } = mapPreferredSessions(omitEmpty(schedule));
  const sparseAvailability = pruneAvailability(availability);
  const cleaned = sparseAvailability ? { ...rest, availability: sparseAvailability } : rest;
  return Object.keys(cleaned).length > 0 ? cleaned : undefined;
}

// Resolves the goal's target-time radio (form-only field, never part of the
// contract) plus its structured hours/minutes/seconds entry into the
// schema's three-way `target_time`: the composed specific time, or the
// "finish"/"suggest" literal (ADR 016).
function resolveGoal(goal) {
  const {
    target_time_mode,
    target_time_h,
    target_time_m,
    target_time_s,
    ...rest
  } = goal ?? {};
  const composed = composeStructuredTime({
    h: target_time_h,
    m: target_time_m,
    s: target_time_s,
  });
  const target_time =
    target_time_mode === "finish" || target_time_mode === "suggest"
      ? target_time_mode
      : composed;
  return omitEmpty({ ...rest, target_time });
}

// Resolves a B race's structured time entry the same way as the goal's,
// minus the "suggest" projection - calibration projects a target only for
// the goal, from the build-week count, and there is no defined analogue for
// a mid-plan B race.
function resolveBRace(race) {
  const { target_time_mode, target_time_h, target_time_m, target_time_s, ...rest } =
    race ?? {};
  const composed = composeStructuredTime({
    h: target_time_h,
    m: target_time_m,
    s: target_time_s,
  });
  const target_time = target_time_mode === "finish" ? "finish" : composed;
  return { ...rest, target_time };
}

// Resolves recent_result's structured time entry into `time`.
function resolveRecentResult(recentResult) {
  if (!recentResult) return recentResult;
  const { time_h, time_m, time_s, ...rest } = recentResult;
  const time = composeStructuredTime({ h: time_h, m: time_m, s: time_s });
  return { ...rest, time };
}

// Computes current_fitness.vdot from a resolved recent_result and folds it
// in, mirroring the same Daniels formula compute_vdot uses (parity:
// tests/test_vdot_parity.py) and submitting it as an authoritative field
// (rundrafter's design.md, "VDOT becomes an authoritative intake field,
// verified upstream"). Only added when current_fitness already carries the
// schema's other required fields (weekly_distance, longest_run) - the
// schema requires both whenever the section is present at all, so a vdot
// with neither would never validate.
function withVdot(currentFitness, recentResult) {
  if (
    !currentFitness ||
    currentFitness.weekly_distance === undefined ||
    currentFitness.longest_run === undefined
  ) {
    return currentFitness;
  }
  if (!recentResult?.distance || !recentResult?.time) return currentFitness;
  try {
    const vdot = Math.round(computeVdotFromResult(recentResult) * 100) / 100;
    return { ...currentFitness, vdot };
  } catch {
    return currentFitness;
  }
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

// The Monday-Sunday week block an ISO date string falls in, as a UTC
// midnight Date on that week's Monday. `Date#getUTCDay` is Sunday-indexed
// (0-6); this rebases to the Monday-indexed weekday validate.py's
// `date.weekday()` uses.
function mondayOf(iso) {
  const d = new Date(iso);
  const mondayIndexedWeekday = (d.getUTCDay() + 6) % 7;
  d.setUTCDate(d.getUTCDate() - mondayIndexedWeekday);
  return d;
}

// Counts the Monday-Sunday week blocks spanning `startIso` to `endIso`,
// mirroring validate.py's `_week_count`: a mid-week start's partial first
// week still counts as week 1, so this is not `floor(days / 7)`.
function weekCount(startIso, endIso) {
  return (mondayOf(endIso) - mondayOf(startIso)) / 86_400_000 / 7 + 1;
}

// The weekday name an ISO date string falls on, Monday-indexed to match
// DAY_NAMES.
function weekdayOf(iso) {
  return DAY_NAMES[(new Date(iso).getUTCDay() + 6) % 7];
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

// Cross-field product rules the schema can't express (see rundrafter's
// docs/webform-architecture.md). Mirrors rundrafter's stage 1
// (validate.py / contracts.md) rule-for-rule. `formState.weekly_schedule`
// here is the already-expanded {availability, preferred_sessions} shape,
// not the raw tri-state grid.
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

  // A preferred session landing on a resolver-derived rest day can only be
  // caught once the resolver has run (validate.py's
  // _validate_resolved_schedule), which this form can't do; an
  // under-constrained grid is generally a resolver-side warning
  // (SCHEDULE_UNDER_CONSTRAINED) this form can't check either - except the
  // 5-or-more-unticked-days case handled as a warning below, which is
  // guaranteed regardless of what the resolver decides.
  //
  // Upstream's LONG_RUN_DAY_UNAVAILABLE and PREFERRED_SESSION_ON_UNAVAILABLE_DAY
  // (a preferred session pinned to a day whose both halves are unticked) are
  // NOT re-implemented here, unlike stage 1's other schedule checks: a
  // session can only exist in a grid cell that is itself in the "session"
  // state, which is by definition not "unavailable", so a day can never be
  // fully unavailable (both halves unticked) while also carrying a
  // preferred session on it - the tri-state grid makes the contradiction
  // structurally unreachable, the same reason SESSION_TIME_UNAVAILABLE below
  // is upstream-only. They stay reachable upstream only via a hand-edited
  // intake.json, whose `availability` and `preferred_sessions` are
  // independent top-level keys with no such coupling.
  //
  // There is no `long_run_day` override field any more (ADR 019) - a
  // `type: "long"` entry in preferred_sessions is the only way to pin the
  // long-run day, so at most one is allowed (mirrors validate.py's
  // MULTIPLE_LONG_RUN_ENTRIES, which - unlike the two checks above - has no
  // dependency on availability and stays fully reachable through the grid).
  const longEntries = (schedule.preferred_sessions ?? []).filter((session) =>
    preferredTypes(session).includes("long"),
  );
  if (longEntries.length > 1) {
    errors.push(
      'weekly_schedule.preferred_sessions has more than one type: "long"' +
        " entry; at most one is allowed to pin the long-run day.",
    );
  }

  validateSessionTypePresent(schedule.preferred_sessions, errors);
  validateDuplicateDaySessions(schedule.preferred_sessions, errors);

  errors.push(
    ...validateFlexibleTypes(
      schedule.preferred_sessions,
      (session) => `Weekly session "${session.day || session.description || "entry"}"`,
    ),
  );
  errors.push(
    ...validateFlexibleTypes(
      formState.other_events,
      (evt) => `Other event on ${evt.date || "unknown date"}`,
    ),
  );
  errors.push(
    ...validateSessionRanges(schedule.preferred_sessions, "Weekly session"),
  );
  errors.push(...validateSessionRanges(formState.other_events, "Other event"));

  validatePlanWindow(goal, errors);
  validateRunDayFloor(schedule, errors);
  validateQualityTouchpoints(schedule.preferred_sessions, errors);

  return errors;
}

// Mirrors validate.py's _validate_duplicate_day_sessions
// (MULTIPLE_SESSIONS_ON_DAY). A weekday carries one session, and two
// entries on it are resolved inconsistently downstream - expand.py's
// _find_preferred takes the first, resolve.py's time-of-day map the last -
// so an accepted pair schedules one entry's session in the other's half
// and drops the second silently. Rejected regardless of time_of_day: the
// plan holds one session per date, so distinct halves don't make both
// schedulable. Unlike SESSION_TIME_UNAVAILABLE, the grid does *not* make
// this unreachable - a session cell in each half of one day is exactly
// what the grid invites, which is why the mirror earns its keep here.
function validateDuplicateDaySessions(preferred, errors) {
  const byDay = new Map();
  for (const session of preferred ?? []) {
    if (!byDay.has(session.day)) byDay.set(session.day, []);
    byDay.get(session.day).push(session);
  }

  for (const day of DAY_NAMES) {
    const sessions = byDay.get(day);
    if (!sessions || sessions.length < 2) continue;
    const halves = sessions.map((s) => s.time_of_day).join(" and ");
    errors.push(
      `${day} has a session in both its ${halves} cells, but a day carries` +
        ' at most one session. Set one cell back to "Available" - the plan' +
        " still uses an available half for easy volume, so you keep the slot," +
        " just not the pin.",
    );
  }
}

// A grid cell switched to "Has a session" with no type ticked assembles to
// a preferred_sessions entry with no `type`, which the schema's `required`
// then rejects. Ajv reports that against the *assembled array index*
// (`weekly_schedule.preferred_sessions.0.type`), a path no field on the
// page carries - the grid's inputs are named by day and half - so the
// runner gets a summary-only message naming a field they cannot find.
// Catching it here instead, before the Ajv pass, names the cell itself.
// No upstream analogue: stage 1 sees only the assembled array, where
// SCHEMA_INVALID against that same index is the whole story.
function validateSessionTypePresent(preferred, errors) {
  for (const session of preferred ?? []) {
    if (preferredTypes(session).length > 0) continue;
    errors.push(
      `The ${session.day} ${session.time_of_day} cell is marked as carrying a` +
        " session, but no session type is ticked. Tick at least one type, or" +
        ' set the cell back to "Available".',
    );
  }
}

// Mirrors validate.py's _validate_flexible_types (FLEXIBLE_TYPE_INCLUDES_LONG,
// FLEXIBLE_TYPE_MIXES_MODES, FLEXIBLE_SKIP_TAILORING_UNSUPPORTED). An entry
// offering several types leaves the pick to the per-week (or per-event)
// selection, but the pipeline still settles its *structural* role once for
// the whole plan - whether it pins the long run, whether it's a running
// commitment, and whether a coach owns its detail - so a set that leaves
// one of those unanswerable is rejected here. Single-type entries are
// untouched. Shared between weekly_schedule.preferred_sessions and
// other_events, whose `type` field accepts the same scalar-or-multi-type-
// array form; `describe` renders each entry's identifying prefix for a
// message (e.g. `Weekly session "Tuesday"`).
function validateFlexibleTypes(entries, describe) {
  const errors = [];
  for (const entry of entries ?? []) {
    const types = preferredTypes(entry);
    if (types.length < 2) continue;
    const where = describe(entry);
    const offered = types.join(", ");

    if (types.includes("long")) {
      errors.push(
        `${where} offers several types (${offered}), one of them the long run. The long run pins your long-run day for the whole plan, so it can't be one option among several - give it a day of its own.`,
      );
    }

    const nonRunning = types.filter((type) => NON_RUNNING_TYPES.has(type));
    if (nonRunning.length > 0 && nonRunning.length < types.length) {
      errors.push(
        `${where} mixes running and non-running types (${offered}). Rest days are placed once for the whole plan and need a definite answer to whether the day is a running day, so a set of types must be either all running or all non-running.`,
      );
    }

    const skippingTailoring = entry.skip_tailoring === true || entry.tailored === false;
    if (skippingTailoring && !types.every((t) => SKIP_TAILORABLE_TYPES.has(t))) {
      errors.push(
        `${where} skips tailoring but offers a type with no detail to hand over (${offered}). Skipping tailoring promises a coach owns that day's detail, so every type offered must be one of: ${[...SKIP_TAILORABLE_TYPES].sort().join(", ")}.`,
      );
    }
  }
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

// Mirrors validate.py's _validate_plan_window: rejects a plan window
// shorter than base + minimum build + taper. A marathon goal counts *both*
// base phases (phase_weeks.base and phase_weeks.marathon_base) - both are
// standing phases in the marathon sequence; only sharpening is optional
// and the floor deliberately omits it.
function validatePlanWindow(goal, errors) {
  const distance = goal.distance;
  if (!goal.start_date || !goal.date || !distance || !TAPER_KEY_BY_DISTANCE[distance]) {
    return;
  }
  if (goal.start_date >= goal.date) return; // date ordering already covers this

  let minimum =
    CONSTRAINTS.phase_weeks.base[0] +
    CONSTRAINTS.phase_weeks.build_min +
    CONSTRAINTS.taper_weeks[TAPER_KEY_BY_DISTANCE[distance]];
  if (distance === "marathon") {
    minimum += CONSTRAINTS.phase_weeks.marathon_base[0];
  }

  const available = weekCount(goal.start_date, goal.date);
  if (available < minimum) {
    errors.push(
      `The window from goal.start_date (${goal.start_date}) to goal.date` +
        ` (${goal.date}) is ${available} week(s), fewer than the ${minimum}` +
        ` week(s) a ${distance} goal needs for base, minimum build, and taper.`,
    );
  }
}

// Mirrors validate.py's _validate_run_day_floor: rejects a grid that can
// never reach the peak run-day floor, checkable before the resolver runs -
// the count of weekdays offering at least one available half is an upper
// bound on trainable days no rest-day placement can raise.
function validateRunDayFloor(schedule, errors) {
  const availability = schedule.availability ?? {};
  const trainableUpperBound = DAY_NAMES.filter(
    (day) => !isDayFullyUnavailable(availability, day),
  ).length;
  const floor = CONSTRAINTS.min_run_days_at_peak;
  if (trainableUpperBound < floor) {
    errors.push(
      `The availability grid offers at least one available half on only` +
        ` ${trainableUpperBound} weekday(s), fewer than the ${floor} running` +
        ` days a peak build week needs (schedule.min_run_days_at_peak). No` +
        " rest-day placement can raise this upper bound on trainable days.",
    );
  }
}

// Mirrors validate.py's _validate_quality_touchpoints. The **ceiling**
// counts a pinned type: "long" entry alongside the quality days - the
// methodology states the number that way ("count the long run, any hard
// anchor, *and* the midweek quality together"). **Adjacency** does not: a
// Saturday anchor beside a Sunday long run is the canonical amateur week,
// and the no-adjacent-quality rule governs where the expander places its
// own sessions, not what a runner pins. Adjacency wraps the week
// (Sunday/Monday count as adjacent), since the weekly template repeats.
function validateQualityTouchpoints(preferred, errors) {
  const qualityDays = [
    ...new Set(
      (preferred ?? [])
        .filter((p) => preferredTypes(p).includes("quality"))
        .map((p) => p.day),
    ),
  ].sort((a, b) => DAY_NAMES.indexOf(a) - DAY_NAMES.indexOf(b));
  const longDays = new Set(
    (preferred ?? []).filter((p) => preferredTypes(p).includes("long")).map((p) => p.day),
  );
  const touchpointDays = [...new Set([...qualityDays, ...longDays])].sort(
    (a, b) => DAY_NAMES.indexOf(a) - DAY_NAMES.indexOf(b),
  );

  const ceiling = CONSTRAINTS.max_quality_touchpoints;
  if (touchpointDays.length > ceiling) {
    errors.push(
      `Pinned quality and long-run days (${touchpointDays.join(", ")}) number` +
        ` ${touchpointDays.length}, more than the configured ceiling of` +
        ` ${ceiling} quality touchpoints a week (schedule.max_quality_touchpoints).` +
        " The long run is a touchpoint in its own right.",
    );
  }

  for (let i = 0; i < qualityDays.length; i++) {
    for (let j = i + 1; j < qualityDays.length; j++) {
      const idxA = DAY_NAMES.indexOf(qualityDays[i]);
      const idxB = DAY_NAMES.indexOf(qualityDays[j]);
      const diff = Math.abs(idxA - idxB);
      if (diff === 1 || diff === DAY_NAMES.length - 1) {
        errors.push(
          `Pinned quality days ${qualityDays[i]} and ${qualityDays[j]} are` +
            " adjacent (the weekly template repeats, so Sunday and Monday" +
            " count as adjacent too); quality sessions should not fall on" +
            " consecutive days.",
        );
      }
    }
  }
}

// Every mid-plan dated event: each B race and each other event. Mirrors
// validate.py's _event_entries_for_clash_check - the goal race is
// deliberately excluded (road races and long runs both land on Sundays, so
// including it warned on almost every intake, and the warning carries no
// information there anyway: race week schedules no long run for the race
// to displace).
function eventEntriesForClashCheck(formState) {
  const events = (formState.b_races ?? [])
    .filter((race) => race?.date)
    .map((race) => ({
      section: "b_races",
      label: race.name || "",
      date: race.date,
    }));
  events.push(
    ...(formState.other_events ?? [])
      .filter((evt) => evt?.date)
      .map((evt) => ({
        section: "other_events",
        label: preferredTypes(evt).join("/"),
        date: evt.date,
      })),
  );
  return events;
}

// Mirrors validate.py's _validate_event_clashes: warns, without blocking,
// when a mid-plan event lands on a weekday with no available half or a
// weekday carrying a preferred session. The event always wins - expand.py
// schedules it on its date regardless of the grid or any pinned session it
// displaces - so this is advisory only.
function validateEventClashes(formState, schedule, warnings) {
  const availability = schedule.availability ?? {};
  const preferred = schedule.preferred_sessions ?? [];
  const preferredByDay = new Map();
  for (const p of preferred) {
    if (!preferredByDay.has(p.day)) preferredByDay.set(p.day, []);
    preferredByDay.get(p.day).push(p);
  }

  for (const { section, label, date } of eventEntriesForClashCheck(formState)) {
    const weekday = weekdayOf(date);

    if (isDayFullyUnavailable(availability, weekday)) {
      warnings.push(
        `${section} event '${label}' on ${date} falls on ${weekday}, which` +
          " has no available half in the availability grid. The event takes" +
          " precedence and will still be scheduled on that date.",
      );
      continue;
    }

    const clashing = preferredByDay.get(weekday);
    if (clashing) {
      const offered = clashing.map((p) => preferredTypes(p).join("/")).join(", ");
      warnings.push(
        `${section} event '${label}' on ${date} falls on ${weekday}, which` +
          ` carries a preferred session (${offered}). The event takes` +
          " precedence and displaces it that week.",
      );
    }
  }
}

// Mirrors calibrate.py's _goal_consistency: warns, without blocking, when
// the goal-implied VDOT diverges from the runner's current VDOT by more
// than the configured threshold. Skipped for a "finish" or "suggest" goal -
// there's no specific goal pace to compare, and "suggest" is itself
// calibrated from current fitness so it's consistent by construction - and
// deferred until a recent result gives a current VDOT to compare against,
// since fitness is collected after the goal (design.md, "re-evaluated when
// the fitness inputs change").
function validateGoalConsistency(goal, recentResultResolved, warnings) {
  if (!goal.distance) return;
  const mode = goal.target_time_mode ?? "specific";
  if (mode !== "specific") return;
  const targetTime = composeStructuredTime({
    h: goal.target_time_h,
    m: goal.target_time_m,
    s: goal.target_time_s,
  });
  if (!targetTime) return;
  if (!recentResultResolved?.distance || !recentResultResolved?.time) return;

  let currentVdot;
  let goalVdot;
  try {
    currentVdot = computeVdotFromResult(recentResultResolved);
    goalVdot = computeVdot(DISTANCE_METRES[goal.distance], parseTimeToMinutes(targetTime));
  } catch {
    return;
  }

  const threshold = CONSTRAINTS.consistency_threshold_vdot;
  const gap = Math.round((goalVdot - currentVdot) * 100) / 100;
  const roundedGoalVdot = Math.round(goalVdot * 100) / 100;
  const roundedCurrentVdot = Math.round(currentVdot * 100) / 100;

  if (gap < -threshold) {
    warnings.push(
      `Goal of ${targetTime} (${goal.distance}) implies VDOT ${roundedGoalVdot},` +
        ` below your current VDOT of ${roundedCurrentVdot}. Training paces` +
        " reflect current fitness; goal pace is used only for goal-pace segments.",
    );
  } else if (gap > threshold) {
    warnings.push(
      `Goal of ${targetTime} (${goal.distance}) implies VDOT ${roundedGoalVdot},` +
        ` which is ${gap} points above your current VDOT of ${roundedCurrentVdot}.` +
        " Consider a more conservative target or re-testing fitness.",
    );
  }
}

// Non-blocking advisories (see rundrafter's docs/webform-architecture.md's
// "Non-blocking" rules).
function validateWarnings(formState, recentResultResolved) {
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

  validateEventClashes(formState, schedule, warnings);
  validateGoalConsistency(goal, recentResultResolved, warnings);

  return warnings;
}

export function assemble(formState, { now } = {}) {
  const timestamp = now ?? new Date().toISOString();

  const weeklyScheduleRaw = expandGrid(formState.weekly_schedule?.grid);
  const formStateForRules = { ...formState, weekly_schedule: weeklyScheduleRaw };
  const recentResultResolved = resolveRecentResult(formState.recent_result);

  const errors = validateCrossField(formStateForRules);
  const warnings = validateWarnings(formStateForRules, recentResultResolved);

  const bRaces = pruneRepeatingSection(
    (formState.b_races ?? []).map(resolveBRace),
  );
  const otherEvents = pruneRepeatingSection(
    (formState.other_events ?? []).map(collapseSingleType),
  );
  const notes = pruneOptionalObject(formState.notes);
  const weeklySchedule = pruneWeeklySchedule(weeklyScheduleRaw);
  const recentResult = pruneOptionalObject(recentResultResolved);
  const currentFitness = pruneOptionalObject(
    withVdot(formState.current_fitness, recentResultResolved),
  );
  // output.quality_detail defaults to "specific" (the schema's own
  // default), so - matching every other section's sparse-by-construction
  // contract - it's only emitted when the runner picked "generic".
  const output =
    formState.output?.quality_detail === "generic"
      ? { quality_detail: "generic" }
      : undefined;

  const intake = {
    meta: { schema_version: "2", submitted_at: timestamp },
    units: formState.units,
    runner: omitEmpty(formState.runner ?? {}),
    goal: resolveGoal(formState.goal),
    ...(output && { output }),
    ...(currentFitness && { current_fitness: currentFitness }),
    ...(recentResult && { recent_result: recentResult }),
    ...(weeklySchedule && { weekly_schedule: weeklySchedule }),
    ...(bRaces && { b_races: bRaces }),
    ...(otherEvents && { other_events: otherEvents }),
    ...(notes && { notes }),
  };

  return { intake, errors, warnings };
}
