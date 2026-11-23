import {useState} from "react";
import {ErrorSummary, Field} from "./forms";
import {useResource} from "./master";

const localTime = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Asia/Karachi", year: "numeric", month: "2-digit", day: "2-digit",
  hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23",
});

export function Audit() {
  const [form, setForm] = useState({});
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const params = new URLSearchParams([...Object.entries(filters).filter(([, value]) => value), ["page", page]]);
  const {data, error} = useResource("/audit?" + params);
  const field = {values: form, error, change: (key, value) => setForm((prior) => ({...prior, [key]: value}))};
  return <>
    <div className="page-heading"><div><h1>Audit log</h1><p>Review recorded actions. Times use Asia/Karachi.</p></div></div>
    <section className="panel">
      <form className="editor audit-form" onSubmit={(event) => { event.preventDefault(); setFilters(form); setPage(1); }}>
        <ErrorSummary error={error} />
        <div className="form-grid">
          <Field {...field} name="username" label="Actor username" maxLength={40} />
          <Field {...field} name="action" label="Action code" maxLength={40} hint="For example, login_failed or schedule_published." />
          <Field {...field} name="from_time" label="From (PKT)" type="datetime-local" />
          <Field {...field} name="to_time" label="To (PKT)" type="datetime-local" />
        </div>
        <div className="form-actions">
          <button className="primary">Apply filters</button>
          <button className="secondary" type="button" onClick={() => { setForm({}); setFilters({}); setPage(1); }}>Clear</button>
        </div>
      </form>
      {!data && !error && <p role="status">Loading audit events…</p>}
      {data?.items.length === 0 && <p>No audit events match these filters.</p>}
      {data?.items.map((row) => <article className="version-row" key={row.log_id} aria-label={row.action}>
        <div><strong>{row.action.replaceAll("_", " ")}</strong> <span className="muted">{row.action}</span>
          <p>{row.username || "Unknown actor"} · {row.entity_type || "—"} {row.entity_id ?? ""}</p>
          {row.details && <p>{row.details}</p>}</div>
        <time dateTime={row.created_at}>{localTime.format(new Date(row.created_at))}</time>
      </article>)}
      {data && data.total > 25 && <div className="pager">
        <button className="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {Math.ceil(data.total / 25)}</span>
        <button className="secondary" disabled={page * 25 >= data.total} onClick={() => setPage(page + 1)}>Next</button>
      </div>}
    </section>
  </>;
}

