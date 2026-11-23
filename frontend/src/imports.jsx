import {useRef, useState} from "react";
import {downloadFile, request} from "./api";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";

const templates = [
  ["courses", "Courses", "Use department code and enter weekly lecture and lab hours."],
  ["instructors", "Instructors", "Use department code and the instructor’s unique email and teaching-hour limits."],
  ["rooms", "Rooms", "Use Lecture, Lab or Exam Hall for room type. Enter seat capacity."],
  ["batches", "Batches", "Use department code, programme code, year, section and student count."],
  ["offerings", "Offerings", "Match a term name, course code, programme, year, section and instructor email."],
  ["enrollments", "Enrollments", "Match a saved offering and the Student account’s username."],
];

export function ImportWizard() {
  const [entity, select] = useState("courses");
  const [file, setFile] = useState(null);
  const attempt = useRef(null);
  const [preview, setPreview] = useState(null);
  const [error, setError] = useState(null);
  const [pending, setPending] = useState(false);
  const [page, setPage] = useState(0);

  async function perform(operation) {
    setError(null);
    setPending(true);
    try {
      await operation();
    } catch (failure) {
      setError(failure);
    } finally {
      setPending(false);
    }
  }

  function upload(event) {
    event.preventDefault();
    setPage(0);
    perform(async () => {
      if (file.size > 10 * 1024 * 1024) throw new Error("Choose a CSV file of 10 MB or less.");
      if (!attempt.current) attempt.current = crypto.randomUUID();
      const form = new FormData();
      form.append("request_token", attempt.current);
      form.append("file", file);
      setPreview(await request("/import/" + entity, {method: "POST", body: form}));
    });
  }

  function finish(action) {
    perform(async () => setPreview(await request("/import/previews/" + preview.key + "/" + action, {method: "POST"})));
  }

  const rows = preview?.rejected.slice(page * 25, (page + 1) * 25);
  return <>
    <div className="page-heading"><div><h1>Import CSV</h1><p>Validate a UTF-8 CSV before adding records.</p></div></div>
    <section className="panel editor">
      <ErrorSummary error={error} />
      {!preview && <form className="editor" onSubmit={upload}>
        <Field name="entity" label="Import type" values={{entity}} change={(_, value) => {
          select(value); attempt.current = null;
        }} options={templates.map(([value, label]) => ({value, label}))} />
        <p>{templates.find(([value]) => value === entity)[2]}</p>
        <button type="button" className="secondary" disabled={pending} onClick={() =>
          perform(() => downloadFile("/import/templates/" + entity, entity + ".csv"))}>Download template</button>
        <div className="field">
          <label htmlFor="csv-upload">CSV file</label>
          <input id="csv-upload" type="file" accept=".csv,text/csv" required aria-describedby="csv-hint"
            onChange={(event) => { setFile(event.target.files[0] || null); attempt.current = null; }} />
          <small id="csv-hint">UTF-8, up to 10 MB</small>
        </div>
        <FormActions action="Preview import" busy={pending} />
      </form>}
      {preview?.state === "Pending" && <>
        <h2>{preview.filename}</h2>
        <dl className="term-counts">
          <div><dt>Rows read</dt><dd>{preview.total}</dd></div>
          <div><dt>Valid rows</dt><dd>{preview.valid_count}</dd></div>
          <div><dt>Rejected rows</dt><dd>{preview.rejected.length}</dd></div>
        </dl>
        {!!rows.length && <ul className="conflicts">{rows.map((row) => <li key={row.line}>
          <strong>Line {row.line}</strong>
          {row.issues.map((issue, index) => <p key={index}>{issue.column} · {issue.reason}</p>)}
        </li>)}</ul>}
        {preview.rejected.length > 25 && <div className="pager">
          <button className="secondary" disabled={!page} onClick={() => setPage(page - 1)}>Previous</button>
          <span>Page {page + 1}</span>
          <button className="secondary" disabled={(page + 1) * 25 >= preview.rejected.length}
            onClick={() => setPage(page + 1)}>Next</button>
        </div>}
        <div className="form-actions">
          <button className="primary" disabled={pending || !preview.valid_count} onClick={() => finish("confirm")}>
            {preview.rejected.length ? "Import valid rows" : "Confirm import"}
          </button>
          <button className="secondary" disabled={pending} onClick={() => finish("cancel")}>Cancel import</button>
        </div>
      </>}
      {preview && preview.state !== "Pending" && <>
        <p role="status">{preview.state === "Confirmed" ? preview.valid_count + " record(s) imported." : "Import cancelled."}</p>
        <button className="secondary" onClick={() => { setPreview(null); setFile(null); attempt.current = null; }}>Start another import</button>
      </>}
    </section>
  </>;
}

