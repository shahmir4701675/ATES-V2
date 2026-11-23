import {useState} from "react";
import {request} from "./api";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";
import {useResource} from "./master";

const required = new Set(["H01", "H02", "H03", "H08", "E01", "E04", "E05"]);
const titles = {
  H01: "Instructor clashes", H02: "Room clashes", H03: "Batch clashes", H04: "Room capacity",
  H05: "Room type", H06: "Instructor availability", H07: "Blocked slots", H08: "Weekly session demand",
  H09: "Consecutive labs", H10: "Teaching-hour limits", S01: "Batch idle gaps", S02: "Session spread",
  S03: "Batch sessions per day", S04: "Consecutive teaching slots", S05: "Previous version stability",
  S06: "Room fit", E01: "Shared students", E02: "Exams per student per day", E03: "Seat allocation",
  E04: "Exclusive exam rooms", E05: "Exam coverage", ES01: "Batch exam spread",
  ES02: "Number of exam rooms", ES03: "Rooms in one building",
};

export function Settings() {
  const {data: references, error} = useResource("/api/master/references");
  const [term, selectTerm] = useState("");
  const [tab, selectTab] = useState("configs");
  const termId = term || (references?.terms.find((row) => row.status === "Active") || references?.terms[0])?.term_id;
  const editable = references?.terms.find((row) => row.term_id === Number(termId))?.status !== "Closed";
  return <>
    <div className="page-heading"><h1>Constraints and settings</h1></div>
    <ErrorSummary error={error} />
    {references && !termId && <p>Add an academic term to configure its scheduling rules.</p>}
    {termId && <>
      <div className="term-select"><Field name="term_id" label="Academic term" values={{term_id: termId}}
        change={(_, value) => selectTerm(value)}
        options={references.terms.map((row) => ({value: row.term_id, label: row.name}))} /></div>
      <div className="form-actions section-nav">
        <button className={tab === "configs" ? "primary" : "secondary"} onClick={() => selectTab("configs")}>Configurations</button>
        <button className={tab === "exams" ? "primary" : "secondary"} onClick={() => selectTab("exams")}>Exam sessions</button>
        <button className={tab === "courses" ? "primary" : "secondary"} onClick={() => selectTab("courses")}>Examinable courses</button>
      </div>
      {tab === "configs" ? <Configurations key={termId} termId={termId} editable={editable} />
        : tab === "exams" ? <ExamSessions key={termId} termId={termId} editable={editable} />
        : <ExamCourses key={termId} termId={termId} editable={editable} />}
    </>}
  </>;
}

function ExamCourses({termId, editable}) {
  const path = "/terms/" + termId + "/exam-courses";
  const [revision, refresh] = useState(0);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState(null);
  const {data, error} = useResource(path, revision);
  async function update(row, included) {
    setBusy(true);
    setFailure(null);
    try {
      await request(path + "/" + row.course_id, {method: "PUT", body: {included}});
      refresh((previous) => previous + 1);
    } catch (problem) {
      setFailure(problem);
    } finally {
      setBusy(false);
    }
  }
  return <section className="panel">
    <div className="section-heading"><div><h2>Examinable courses</h2>
      <p>Choose which courses to include in future exam runs for this term.</p></div></div>
    <ErrorSummary error={error || failure} />
    {!data && !error && <p role="status">Loading courses…</p>}
    {data?.length === 0 && <p>No courses have been offered in this term.</p>}
    {data?.map((row) => <label className="version-row" key={row.course_id}>
      <span><strong>{row.course_code}</strong> · {row.title}</span>
      <span><input type="checkbox" checked={row.included} onChange={(event) => update(row, event.target.checked)}
        disabled={!editable || busy} /> Include in exams</span>
    </label>)}
  </section>;
}

function Configurations({termId, editable}) {
  const [selected, select] = useState(null);
  const [revision, refresh] = useState(0);
  const {data, error} = useResource("/configs?term_id=" + termId, revision);
  function done() { select(null); refresh((prior) => prior + 1); }
  return <section className="panel">
    <ErrorSummary error={error} />
    {selected?.mode === "rules" && <Rules config={selected.row} editable={editable} cancel={done} />}
    {selected && selected.mode !== "rules" && <ConfigForm key={selected.mode} item={selected} termId={termId} done={done} />}
    {!selected && <>
      <div className="section-heading"><h2>Configurations</h2>
        {editable && <button className="primary" onClick={() => select({mode: "new"})}>Add configuration</button>}</div>
      {!data && !error && <p role="status">Loading configurations…</p>}
      {data?.map((row) => <article className="version-row" key={row.config_id} aria-label={row.name + " " + row.schedule_type}>
        <div><strong>{row.name} · {row.schedule_type}</strong><p>{row.solver_time_limit_s}s · Seed {row.random_seed}</p></div>
        <div className="row-tools">
          <button className="text-button" onClick={() => select({mode: "rules", row})}>Rules</button>
          {editable && <>
            <button className="text-button" onClick={() => select({mode: "edit", row})}>Edit</button>
            <button className="text-button" onClick={() => select({mode: "clone", row})}>Clone</button>
            {row.name !== "Default" && <button className="text-button" onClick={() => select({mode: "remove", row})}>Delete</button>}
          </>}
        </div>
      </article>)}
    </>}
  </section>;
}

function ConfigForm({item, termId, done}) {
  const {mode, row} = item;
  const remove = mode === "remove";
  const edit = mode === "edit";
  const clone = mode === "clone";
  const title = {remove: "Delete configuration", edit: "Edit configuration", clone: "Clone configuration", new: "Add configuration"}[mode];
  const form = useForm({
    name: edit ? row.name : "", schedule_type: row?.schedule_type || "Timetable",
    solver_time_limit_s: row?.solver_time_limit_s || 120, random_seed: row?.random_seed ?? 1,
    lab_block_slots: row?.lab_block_slots ?? "",
  }, async (values) => {
    const base = {name: values.name, solver_time_limit_s: values.solver_time_limit_s, random_seed: values.random_seed,
      lab_block_slots: Number(values.lab_block_slots) || null};
    const body = edit ? base : {...base, term_id: Number(termId), schedule_type: values.schedule_type, ...(clone && {clone_id: row.config_id})};
    await request("/configs" + (edit || remove ? "/" + row.config_id : ""), {
      method: remove ? "DELETE" : edit ? "PUT" : "POST", body: remove ? undefined : body,
    });
    done();
  });
  return <form className="editor" onSubmit={form.handle}>
    <h2>{title}</h2>
    <ErrorSummary error={form.error} />
    {remove ? <p>Delete {row.name}? Future runs will no longer be able to select it.</p> : <>
      <Field {...form} name="name" label="Configuration name" required maxLength={60} readOnly={edit && row.name === "Default"} />
      {mode === "new" && <Field {...form} name="schedule_type" label="Schedule type"
        options={["Timetable", "Exam"].map((value) => ({value, label: value}))} />}
      {!clone && <>
        <Field {...form} name="solver_time_limit_s" label="Time limit in seconds" required type="number" min={10} max={600} />
        <Field {...form} name="random_seed" label="Random seed" required type="number" min={0} max={2147483647} />
        {form.values.schedule_type === "Timetable" && <Field {...form} name="lab_block_slots" label="Slots per lab block"
          type="number" min={1} max={48} hint="Leave empty for one continuous lab block per offering." />}
      </>}
    </>}
    <FormActions action={mode === "new" || edit ? "Save configuration" : title} busy={form.busy} cancel={done} />
  </form>;
}

function Rules({config, editable, cancel}) {
  const {data, error} = useResource("/configs/" + config.config_id + "/rules");
  return <>
    <ErrorSummary error={error} />
    {data ? <RuleEditor rules={data} config={config} editable={editable} cancel={cancel} />
      : !error && <p role="status">Loading rules…</p>}
  </>;
}

function RuleEditor({rules, config, editable, cancel}) {
  const [confirmed, confirm] = useState(false);
  const form = useForm(Object.fromEntries(rules.flatMap((row) => [
    [row.rule_code + ".enabled", row.is_enabled], [row.rule_code + ".weight", row.weight],
    [row.rule_code + ".param", row.param_value],
  ])), async (values) => {
    await request("/configs/" + config.config_id + "/rules", {method: "PUT", body: {
      confirmed_disable: confirmed, rules: rules.map((row) => ({
        rule_code: row.rule_code, is_enabled: values[row.rule_code + ".enabled"], weight: values[row.rule_code + ".weight"],
        param_value: row.param_value === null ? null : values[row.rule_code + ".param"],
      })),
    }});
    cancel();
  });
  const disabling = rules.filter((row) => row.rule_type === "Hard" && row.is_enabled && !form.values[row.rule_code + ".enabled"]);
  return <form className="grid-form" onSubmit={form.handle}>
    <h2>{config.name} · {config.schedule_type} rules</h2>
    <ErrorSummary error={form.error} />
    {rules.map((row) => <fieldset className="rule-row" key={row.rule_code}>
      <legend>{row.rule_code} · {titles[row.rule_code]}</legend>
      <label><input type="checkbox" disabled={!editable || required.has(row.rule_code)}
        checked={form.values[row.rule_code + ".enabled"]}
        onChange={(event) => { form.change(row.rule_code + ".enabled", event.target.checked); confirm(false); }} /> {
          required.has(row.rule_code) ? "Always enabled" : "Enabled"
        }</label>
      {row.rule_type === "Soft" && <Field {...form} name={row.rule_code + ".weight"} label={row.rule_code + " weight"}
        required type="number" min={0} max={10} readOnly={!editable} />}
      {row.param_value !== null && <Field {...form} name={row.rule_code + ".param"} label={row.rule_code + " limit"}
        required type="number" min={1} max={32767} readOnly={!editable} />}
    </fieldset>)}
    {!!disabling.length && <label className="notice"><input type="checkbox" checked={confirmed}
      onChange={(event) => confirm(event.target.checked)} /> Allow future runs to violate these rules {
        disabling.map((row) => row.rule_code).join(", ")
      }.</label>}
    {editable ? <FormActions action="Save rules" busy={form.busy} cancel={cancel} />
      : <button className="secondary" type="button" onClick={cancel}>Back to configurations</button>}
  </form>;
}

function ExamSessions({termId, editable}) {
  const [revision, refresh] = useState(0);
  const [editing, edit] = useState(null);
  const {data, error} = useResource("/terms/" + termId + "/exam-slots", revision);
  function done() { edit(null); refresh((prior) => prior + 1); }
  return <section className="panel">
    <ErrorSummary error={error} />
    {editing ? <ExamSessionForm termId={termId} session={editing} done={done} cancel={() => edit(null)} /> : <>
      <div className="section-heading"><h2>Exam sessions</h2>
        {editable && <button className="primary" onClick={() => edit({})}>Add exam session</button>}</div>
      {data?.length === 0 && <p>No exam sessions have been added.</p>}
      {data?.map((row) => <article className="version-row" key={row.exam_slot_id}>
        <div><strong>{row.exam_date.split("-").reverse().join("/")} · {row.start_time.slice(0, 5)}–{row.end_time.slice(0, 5)}</strong>
          {row.label && <p>{row.label}</p>}</div>
        {editable && <button className="text-button" onClick={() => edit(row)}>Edit</button>}
      </article>)}
    </>}
  </section>;
}

function ExamSessionForm({termId, session, done, cancel}) {
  const key = session.exam_slot_id;
  const form = useForm({...session, start_time: session.start_time?.slice(0, 5), end_time: session.end_time?.slice(0, 5)},
    async ({exam_date, label, start_time, end_time}) => {
      await request("/terms/" + termId + "/exam-slots" + (key ? "/" + key : ""),
        {method: key ? "PUT" : "POST", body: {exam_date, label: label || "", start_time, end_time}});
      done();
    });
  return <form className="editor" onSubmit={form.handle}>
    <h2>{key ? "Edit exam session" : "Add exam session"}</h2>
    <ErrorSummary error={form.error} />
    <Field {...form} name="exam_date" label="Exam date" required type="date" />
    <div className="form-grid">
      <Field {...form} name="start_time" label="Start time" required type="time" />
      <Field {...form} name="end_time" label="End time" required type="time" />
    </div>
    <Field {...form} name="label" label="Session label" maxLength={30} />
    <FormActions action="Save exam session" busy={form.busy} cancel={cancel} />
  </form>;
}

