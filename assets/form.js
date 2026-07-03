import { assemble } from "./assemble.js";
import { downloadIntake } from "./handoff.js";
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

function setupRepeatingGroup(listId, templateId, addButtonId, onRowAdded) {
  const list = document.getElementById(listId);
  const template = document.getElementById(templateId);
  const addButton = document.getElementById(addButtonId);
  if (!list || !template || !addButton) return;

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
    });
    list.appendChild(row);
    onRowAdded?.(row);
  }

  addButton.addEventListener("click", addRow);
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

function renderErrors(container, messages) {
  container.innerHTML = "";
  if (messages.length === 0) return;
  const list = document.createElement("ul");
  for (const message of messages) {
    const item = document.createElement("li");
    item.textContent = message;
    list.appendChild(item);
  }
  container.appendChild(list);
}

function handleSubmit(event) {
  event.preventDefault();

  const form = event.currentTarget;
  const errorContainer = document.getElementById("form-errors");
  const formState = gatherFormState(form);
  const { intake, errors } = assemble(formState);

  if (errors.length > 0) {
    renderErrors(errorContainer, errors);
    return;
  }

  const Ajv2020 = window.ajv2020.default;
  const ajv = new Ajv2020({ allErrors: true });
  const validate = ajv.compile(schema);
  const valid = validate(intake);

  if (!valid) {
    const messages = validate.errors.map(
      (err) => `${err.instancePath || "(root)"} ${err.message}`,
    );
    renderErrors(errorContainer, messages);
    return;
  }

  renderErrors(errorContainer, []);
  downloadIntake(intake);
}

const form = document.getElementById("intake-form");
if (form) {
  form.addEventListener("submit", handleSubmit);
  const updateUnitLabels = setupUnitLabels(form);
  setupRepeatingGroup(
    "preferred-sessions-list",
    "preferred-session-template",
    "add-preferred-session",
    () => updateUnitLabels(),
  );
}
