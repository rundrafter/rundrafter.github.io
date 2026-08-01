// Client-side Daniels VDOT calculation, kept in parity with rundrafter's
// compute_vdot (src/rundrafter/calibrate/calibrate.py) by
// tests/test_vdot_parity.py - a change to either implementation must move
// with the other (design.md, "Client-side VDOT parity is an executable
// test, not a review item").

export const DISTANCE_METRES = {
  "5k": 5000,
  "10k": 10000,
  half: 21097,
  marathon: 42195,
};

// Parses H:MM:SS, MM:SS, or M:SS into decimal minutes, mirroring
// calibrate.py's parse_time_to_minutes.
export function parseTimeToMinutes(t) {
  const parts = t.split(":").map(Number);
  if (parts.length === 3) {
    const [h, m, s] = parts;
    return h * 60 + m + s / 60;
  }
  if (parts.length === 2) {
    const [m, s] = parts;
    return m + s / 60;
  }
  throw new Error(`Cannot parse time: ${t}`);
}

function vo2FromVelocity(v) {
  return -4.6 + 0.182258 * v + 0.000104 * v * v;
}

function effortFraction(tMinutes) {
  return (
    0.8 +
    0.1894393 * Math.exp(-0.012778 * tMinutes) +
    0.2989558 * Math.exp(-0.1932605 * tMinutes)
  );
}

// Computes VDOT from a race distance (metres) and finish time (minutes),
// mirroring calibrate.py's compute_vdot.
export function computeVdot(distanceM, timeMin) {
  const v = distanceM / timeMin;
  return vo2FromVelocity(v) / effortFraction(timeMin);
}

// Computes VDOT directly from a recent_result-shaped object
// ({ distance, time }), the form's actual entry point.
export function computeVdotFromResult({ distance, time }) {
  const distanceM = DISTANCE_METRES[distance];
  const timeMin = parseTimeToMinutes(time);
  return computeVdot(distanceM, timeMin);
}
