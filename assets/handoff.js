// Single configured return address (ADR 003) - the mailto: recipient and the
// on-screen plain-text fallback both read from here, so changing it is a
// one-place edit.
export const RETURN_EMAIL = "eric.parkin@protonmail.com";

export function downloadIntake(intake, filename = "intake.json") {
  const blob = new Blob([JSON.stringify(intake, null, 2)], {
    type: "application/json",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function composeSubject(intake) {
  const parts = [intake.runner?.name, intake.goal?.race].filter(Boolean);
  return parts.length > 0
    ? `RunDrafter intake — ${parts.join(", ")}`
    : "RunDrafter intake";
}

function composeBody() {
  return [
    "Hi,",
    "",
    "Attached is my intake.json for RunDrafter, downloaded from the intake form.",
    "",
    "Thanks!",
  ].join("\n");
}

export function buildMailtoUrl(intake, { recipient = RETURN_EMAIL } = {}) {
  const params = { subject: composeSubject(intake), body: composeBody() };
  const query = Object.entries(params)
    .map(([key, value]) => `${key}=${encodeURIComponent(value)}`)
    .join("&");
  return `mailto:${recipient}?${query}`;
}
