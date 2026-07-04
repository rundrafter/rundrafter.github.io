import { assemble } from "./assemble.js";
import { downloadIntake, buildMailtoUrl, RETURN_EMAIL } from "./handoff.js";
import schema from "./schema.js";

function setPath(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    const nextIsIndex = /^\d+$/.test(parts[i + 1]);
    cur[part] ??= nextIsIndex ? [] : {};
    cur = cur[part];
  }
  cur[parts[parts.length - 1]] = value;
}

export function gatherFormState(form) {
  const state = {};
  const groupCounts = {};
  form.querySelectorAll('input[type="checkbox"]').forEach((el) => {
    groupCounts[el.name] = (groupCounts[el.name] || 0) + 1;
  });

  const handledCheckboxNames = new Set();

  form.querySelectorAll("input, select, textarea").forEach((el) => {
    if (!el.name) return;

    if (el.type === "checkbox") {
      if (handledCheckboxNames.has(el.name)) return;
      handledCheckboxNames.add(el.name);
      if (groupCounts[el.name] > 1) {
        const values = Array.from(
          form.querySelectorAll(
            `input[type="checkbox"][name="${el.name}"]:checked`,
          ),
        ).map((box) => box.value);
        setPath(state, el.name, values);
      } else {
        setPath(state, el.name, el.checked);
      }
      return;
    }

    if (el.type === "radio") {
      if (!el.checked) return;
      setPath(state, el.name, el.value);
      return;
    }

    if (el.type === "number") {
      setPath(state, el.name, el.value === "" ? undefined : el.valueAsNumber);
      return;
    }

    setPath(state, el.name, el.value);
  });

  return state;
}

function setupRepeatingGroup(
  listId,
  templateId,
  addButtonId,
  { onRowAdded, maxRows } = {},
) {
  const list = document.getElementById(listId);
  const template = document.getElementById(templateId);
  const addButton = document.getElementById(addButtonId);
  if (!list || !template || !addButton) return;

  function updateAddButton() {
    addButton.disabled = maxRows != null && list.children.length >= maxRows;
  }

  function reindex() {
    Array.from(list.children).forEach((row, index) => {
      row.querySelectorAll("[name]").forEach((el) => {
        el.name = el.name.replace(/\.\d+\./, `.${index}.`);
      });
    });
  }

  function addRow() {
    const index = list.children.length;
    const fragment = template.content.cloneNode(true);
    fragment.querySelectorAll("[name]").forEach((el) => {
      el.name = el.name.replace("__INDEX__", index);
    });
    const row = fragment.firstElementChild;
    row.querySelector("[data-remove-row]").addEventListener("click", () => {
      row.remove();
      reindex();
      updateAddButton();
    });
    list.appendChild(row);
    onRowAdded?.(row);
    updateAddButton();
  }

  addButton.addEventListener("click", addRow);
  updateAddButton();
}

function setupUnitLabels(form) {
  function update() {
    const checked = form.querySelector('input[name="units"]:checked');
    const unit = checked ? checked.value : "km";
    form.querySelectorAll("[data-unit-label]").forEach((el) => {
      el.textContent = unit;
    });
  }
  form.querySelectorAll('input[name="units"]').forEach((el) => {
    el.addEventListener("change", update);
  });
  update();
  return update;
}

function setupHealthAcknowledgement(form) {
  const wrapper = document.getElementById("health-acknowledgement");
  const checkboxes = form.querySelectorAll(
    'input[name^="health_screen."][type="checkbox"]',
  );
  if (!wrapper || checkboxes.length === 0) return;

  function update() {
    const anyRaised = Array.from(checkboxes).some((el) => el.checked);
    wrapper.hidden = !anyRaised;
    if (!anyRaised) {
      wrapper.querySelector('input[name="consent.health_acknowledged"]').checked = false;
    }
  }

  checkboxes.forEach((el) => el.addEventListener("change", update));
  update();
}

function clearFieldErrors(form) {
  form.querySelectorAll(".field-error").forEach((el) => el.remove());
  form.querySelectorAll('[aria-invalid="true"]').forEach((el) => {
    el.removeAttribute("aria-invalid");
    el.removeAttribute("aria-describedby");
  });
}

// Marks the field(s) named by a dot-path (e.g. "goal.date", matching Ajv's
// instancePath once converted) as invalid and drops a message right after
// them - the "inline against their fields" half of error surfacing. Falls
// back to summary-only if no field with that name exists (e.g. a repeating
// row's error before the row has been added).
let fieldErrorCount = 0;

function markFieldError(form, path, message) {
  if (!path) return false;
  const fields = form.querySelectorAll(`[name="${CSS.escape(path)}"]`);
  if (fields.length === 0) return false;

  const isGroup = fields.length > 1;
  const anchor = isGroup ? (fields[0].closest("fieldset") ?? fields[0]) : fields[0];

  const note = document.createElement("p");
  note.className = "field-error";
  note.id = `field-error-${fieldErrorCount++}`;
  note.textContent = message;
  anchor.insertAdjacentElement(isGroup ? "beforeend" : "afterend", note);

  fields.forEach((el) => {
    el.setAttribute("aria-invalid", "true");
    el.setAttribute("aria-describedby", note.id);
  });
  if (isGroup) anchor.setAttribute("aria-invalid", "true");
  return true;
}

function ajvPathToFieldName(instancePath) {
  return instancePath.replace(/^\//, "").replace(/\//g, ".");
}

function renderErrors(form, container, errors) {
  clearFieldErrors(form);
  container.innerHTML = "";
  if (errors.length === 0) return;

  const list = document.createElement("ul");
  for (const error of errors) {
    const message =
      typeof error === "string"
        ? error
        : `${error.path ? `${error.path}: ` : ""}${error.message}`;
    markFieldError(form, error.path, message);

    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  }
  container.appendChild(list);
  container.focus();
}

function renderWarnings(container, warnings) {
  container.innerHTML = "";
  if (warnings.length === 0) return;

  const list = document.createElement("ul");
  for (const warning of warnings) {
    const item = document.createElement("li");
    item.textContent = warning;
    list.appendChild(item);
  }
  container.appendChild(list);
}

function showSuccessScreen(form, intake) {
  const successScreen = document.getElementById("success-screen");
  if (!successScreen) return;

  document.getElementById("email-it-in").href = buildMailtoUrl(intake);
  document.getElementById("return-email").textContent = RETURN_EMAIL;
  document.getElementById("download-again").onclick = () =>
    downloadIntake(intake);

  form.hidden = true;
  successScreen.hidden = false;
}

function handleSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const errorContainer = document.getElementById("form-errors");
  const warningContainer = document.getElementById("form-warnings");
  const formState = gatherFormState(form);
  const { intake, errors, warnings } = assemble(formState);

  renderWarnings(warningContainer, warnings);

  if (errors.length > 0) {
    renderErrors(form, errorContainer, errors);
    return;
  }

  const Ajv2020 = window.ajv2020.default;
  const ajv = new Ajv2020({ allErrors: true });
  const validate = ajv.compile(schema);
  const valid = validate(intake);

  if (!valid) {
    const ajvErrors = validate.errors.map((err) => ({
      path: err.instancePath ? ajvPathToFieldName(err.instancePath) : null,
      message: `${err.instancePath || "(root)"} ${err.message}`,
    }));
    renderErrors(form, errorContainer, ajvErrors);
    return;
  }

  renderErrors(form, errorContainer, []);
  downloadIntake(intake);
  showSuccessScreen(form, intake);
}

const form = document.getElementById("intake-form");
if (form) {
  form.addEventListener("submit", handleSubmit);
  const updateUnitLabels = setupUnitLabels(form);
  setupHealthAcknowledgement(form);
  setupRepeatingGroup(
    "preferred-sessions-list",
    "preferred-session-template",
    "add-preferred-session",
    { onRowAdded: () => updateUnitLabels() },
  );
  setupRepeatingGroup("injuries-list", "injury-template", "add-injury");
  setupRepeatingGroup("b-races-list", "b-race-template", "add-b-race", {
    maxRows: 3,
  });
  setupRepeatingGroup(
    "other-events-list",
    "other-event-template",
    "add-other-event",
  );
}
