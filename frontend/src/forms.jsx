import {useEffect, useId, useRef, useState} from "react";
import {fieldName} from "./text";

export function Field({name, label, values, change, error, options, hint, ...props}) {
  const id = useId();
  const message = error?.fields?.[name];
  const describedBy = [hint && id + "-hint", message && id + "-error"].filter(Boolean).join(" ");
  const input = {
    id, name,
    "aria-invalid": message ? true : undefined,
    "aria-describedby": describedBy || undefined,
    value: values[name] ?? "",
    onChange: (event) => change(name, event.target.value),
    ...props,
  };
  return <div className="field">
    <label htmlFor={id}>{label || fieldName(name)}</label>
    {options
      ? <select {...input}>{options.map(({value, label: text}) => <option value={value} key={value}>{text}</option>)}</select>
      : <input {...input} />}
    {hint && <small id={id + "-hint"}>{hint}</small>}
    {message && <small className="field-error" id={id + "-error"}>{message}</small>}
  </div>;
}

export function ErrorSummary({error}) {
  const element = useRef(null);
  useEffect(() => {
    if (error) element.current?.focus();
  }, [error]);
  if (!error) return null;
  return <div className="error-summary" role="alert" tabIndex={-1} ref={element}>
    <strong>{error.message}</strong>
    {!!Object.keys(error.fields || {}).length && <ul>{Object.entries(error.fields).map(([field, message]) =>
      <li key={field}>{fieldName(field)}. {message}</li>
    )}</ul>}
  </div>;
}

export function useForm(initial, submit) {
  const [values, setValues] = useState(initial);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  function change(name, value) {
    setValues((previous) => ({...previous, [name]: value}));
  }
  async function handle(event) {
    event.preventDefault();
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setError(null);
    try {
      await submit(values);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
      submitting.current = false;
    }
  }
  return {values, error, busy, change, handle};
}

export function FormActions({cancel, action, busy}) {
  return <div className="form-actions">
    <button className="primary" disabled={busy}>{busy ? "Saving…" : action}</button>
    {cancel && <button className="secondary" type="button" disabled={busy} onClick={cancel}>Cancel</button>}
  </div>;
}

