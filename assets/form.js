import { assemble } from "./assemble.js";
import { downloadIntake } from "./handoff.js";
import schema from "./schema.js";

function setPath(obj, path, value) {
  const parts = path.split(".");
  let cur = obj;
  for (let i = 0; i < parts.length - 1; i++) {
    cur[parts[i]] ??= {};
    cur = cur[parts[i]];
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
}
