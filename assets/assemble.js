function omitEmpty(obj) {
  const result = {};
  for (const [key, value] of Object.entries(obj)) {
    if (value === undefined || value === null || value === "") continue;
    result[key] = value;
  }
  return result;
}

export function assemble(formState, { now } = {}) {
  const timestamp = now ?? new Date().toISOString();
  const errors = [];

  const intake = {
    meta: { schema_version: "1", submitted_at: timestamp },
    units: formState.units,
    goal: omitEmpty(formState.goal ?? {}),
    recent_result: omitEmpty(formState.recent_result ?? {}),
    current_fitness: omitEmpty(formState.current_fitness ?? {}),
    weekly_schedule: omitEmpty(formState.weekly_schedule ?? {}),
    preferences: omitEmpty(formState.preferences ?? {}),
    health_screen: omitEmpty(formState.health_screen ?? {}),
    consent: omitEmpty({
      ...formState.consent,
      accepted_at: timestamp,
    }),
    output: omitEmpty(formState.output ?? {}),
  };

  return { intake, errors };
}
