import {useEffect, useState} from "react";
import {request} from "./api";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";
import {roles} from "./text";

const pick = (label) => ({value: "", label});
const option = (value, label) => ({value, label});

export function Users({current, notify}) {
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState(null);
  const [action, setAction] = useState(null);
  const [revision, refresh] = useState(0);
  const [error, setError] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams({search, page});
    setError(null);
    request("/api/users?" + params, {signal: controller.signal}).then(setData).catch((failure) => {
      if (failure.name !== "AbortError") setError(failure);
    });
    return () => controller.abort();
  }, [page, search, revision]);

  function saved(message) {
    setAction(null);
    refresh((revision) => revision + 1);
    notify(message);
  }

  if (action?.type === "edit" || action?.type === "new") {
    return <AccountForm account={action.account} cancel={() => setAction(null)} saved={saved} />;
  }
  if (action?.type === "password" || action?.type === "status") {
    return <AccountAction {...action} cancel={() => setAction(null)} saved={saved} />;
  }

  return <>
    <div className="page-heading"><div><h1>User accounts</h1><p>Manage sign-in access and role assignments.</p></div>
      <button className="primary" onClick={() => setAction({type: "new"})}>Add account</button>
    </div>
    <section className="panel" aria-label="Account directory">
      <form className="filter" onSubmit={(event) => { event.preventDefault(); setSearch(query); setPage(1); }}>
        <Field name="search" label="Search accounts" values={{search: query}} change={(_, value) => setQuery(value)}
          placeholder="Name, username, email or role" maxLength={120} />
        <button className="secondary">Search</button>
      </form>
      <ErrorSummary error={error} />
      {!data && !error && <p role="status">Loading accounts…</p>}
      {data && <div className="account-list">
        {data.items.length === 0 && <p>No accounts match this search.</p>}
        {data.items.map((account) => <article className="account-row" key={account.user_id} aria-label={account.username}>
          <div><strong>{account.full_name}</strong><p className="muted">{account.username} · {account.email}</p></div>
          <div><span className="account-role">{account.role}</span> <span className="status-tag">{account.account_status}</span></div>
          <div className="row-tools">
            <button className="text-button" onClick={() => setAction({type: "edit", account})}>Edit</button>
            {account.user_id !== current.user_id && <>
              <button className="text-button" onClick={() => setAction({type: "password", account})}>Reset password</button>
              <button className="text-button" onClick={() => setAction({type: "status", account})}>
                {account.account_status === "Active" ? "Deactivate" : "Reactivate"}
              </button>
            </>}
          </div>
        </article>)}
      </div>}
      {data && data.total > 25 && <div className="pager">
        <button className="secondary" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {Math.ceil(data.total / 25)}</span>
        <button className="secondary" disabled={page * 25 >= data.total} onClick={() => setPage(page + 1)}>Next</button>
      </div>}
    </section>
  </>;
}

function linkPayload(values, role) {
  const entity = {Faculty: "instructor", Student: "batch"}[role];
  if (!entity) return {};
  const key = entity + "_id";
  if (values[key] !== "new") return {[key]: Number(values[key]) || null};
  const fields = entity === "instructor"
    ? ["full_name", "email", "max_daily_hours", "max_weekly_hours"]
    : ["program_code", "batch_year", "section", "strength"];
  const record = Object.fromEntries(fields.map((field) => [field, values[entity + "." + field]]));
  if (values[entity + ".department_id"] === "new") {
    record.department = {code: values[entity + ".department.code"], name: values[entity + ".department.name"]};
  } else {
    record.department_id = Number(values[entity + ".department_id"]) || null;
  }
  return {[entity]: record};
}

function AccountForm({account, cancel, saved}) {
  const [references, setReferences] = useState(null);
  const [loadError, setLoadError] = useState(null);
  useEffect(() => {
    const controller = new AbortController();
    request("/api/users/references", {signal: controller.signal}).then(setReferences).catch((failure) => {
      if (failure.name !== "AbortError") setLoadError(failure);
    });
    return () => controller.abort();
  }, []);
  const form = useForm({
    role: "Coordinator", "instructor.max_daily_hours": 4, "instructor.max_weekly_hours": 18,
    ...account,
  }, async (values) => {
    const {username, full_name, email, role, password} = values;
    const body = {username, full_name, email, role, ...linkPayload(values, role)};
    if (!account) body.password = password;
    await request(account ? "/api/users/" + account.user_id : "/api/users", {method: account ? "PUT" : "POST", body});
    saved(account ? "Account updated." : "Account created.");
  });
  const field = {values: form.values, change: form.change, error: form.error};
  return <>
    <div className="page-heading"><h1>{account ? "Edit account" : "Add account"}</h1></div>
    <form className="panel editor" onSubmit={form.handle}>
      <ErrorSummary error={form.error || loadError} />
      <div className="form-grid">
        <Field {...field} name="username" required maxLength={40} autoComplete="off" />
        <Field {...field} name="full_name" required maxLength={100} />
        <Field {...field} name="email" required type="email" maxLength={120} />
        <Field {...field} name="role" options={roles.map((role) => option(role, role))} />
        {!account && <Field {...field} name="password" label="Initial password" required type="password"
          autoComplete="new-password" hint="Use at least 8 characters." />}
      </div>
      {references
        ? <LinkedRecord field={field} references={references} />
        : !loadError && <p role="status">Loading linked records…</p>}
      <FormActions cancel={cancel} action={account ? "Save account" : "Create account"} busy={form.busy || !references} />
    </form>
  </>;
}

function LinkedRecord({field, references}) {
  const entity = {Faculty: "instructor", Student: "batch"}[field.values.role];
  if (!entity) return null;
  const isInstructor = entity === "instructor";
  const key = entity + "_id";
  const records = references[isInstructor ? "instructors" : "batches"];
  return <fieldset>
    <legend>{isInstructor ? "Instructor link" : "Batch link"}</legend>
    <Field {...field} name={key} required options={[
      pick("Select a record"), ...records.map((record) => option(record[key], isInstructor
        ? record.full_name + " · " + record.email : [record.program_code, record.batch_year, record.section].join(" "))),
      option("new", "Create a " + entity),
    ]} />
    {field.values[key] === "new" && <div className="form-grid linked">
      {isInstructor ? <>
        <Field {...field} name="instructor.full_name" label="Instructor name" required maxLength={100} />
        <Field {...field} name="instructor.email" label="Instructor email" required type="email" maxLength={120} />
        <Field {...field} name="instructor.max_daily_hours" label="Maximum daily hours" required type="number" min={1} />
        <Field {...field} name="instructor.max_weekly_hours" label="Maximum weekly hours" required type="number" min={1} />
      </> : <>
        <Field {...field} name="batch.program_code" label="Programme code" required maxLength={10} />
        <Field {...field} name="batch.batch_year" label="Year" required type="number" min={1900} max={9999} />
        <Field {...field} name="batch.section" label="Section" required maxLength={5} />
        <Field {...field} name="batch.strength" label="Student count" required type="number" min={1} />
      </>}
      <Field {...field} name={entity + ".department_id"} label="Department" required options={[
        pick("Select a department"),
        ...references.departments.map((department) => option(department.department_id, department.name)),
        option("new", "Create a department"),
      ]} />
      {field.values[entity + ".department_id"] === "new" && <>
        <Field {...field} name={entity + ".department.code"} label="Department code" required maxLength={10} />
        <Field {...field} name={entity + ".department.name"} label="Department name" required maxLength={100} />
      </>}
    </div>}
  </fieldset>;
}

function AccountAction({type, account, cancel, saved}) {
  const resetting = type === "password";
  const active = account.account_status !== "Active";
  const title = resetting ? "Reset password" : active ? "Reactivate account" : "Deactivate account";
  const form = useForm({}, async ({password}) => {
    await request("/api/users/" + account.user_id + (resetting ? "/password" : "/status"),
      {method: "PUT", body: resetting ? {password} : {active}});
    saved(resetting ? "Password reset." : active ? "Account reactivated." : "Account deactivated.");
  });
  return <>
    <div className="page-heading"><h1>{title}</h1></div>
    <form className="panel editor" onSubmit={form.handle}>
      <p>{account.full_name} · {account.username}</p>
      <p>{resetting ? "The account’s existing sessions will end." : active
        ? "This user will be able to sign in again." : "This user will be signed out. Their recorded activity will remain available."}</p>
      <ErrorSummary error={form.error} />
      {resetting && <Field {...form} name="password" label="New password" type="password" required
        autoComplete="new-password" hint="Use at least 8 characters." />}
      <FormActions action={title} cancel={cancel} busy={form.busy} />
    </form>
  </>;
}

