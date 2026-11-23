import {useEffect, useState} from "react";
import {request} from "./api";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";

export const weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const displayDate = (date) => date?.split("-").reverse().join("/");
const selectOptions = (items) => items.map((item) => ({value: item, label: item}));
const ref = (key, label, type) => ({key, label, ref: type});
const text = (key, label, maxLength) => ({key, label, props: {maxLength}});
const number = (key, label, min = 1, max = 32767) => ({key, label, props: {type: "number", min, max}});
const status = {key: "is_active", label: "Status", options: [
  {value: "true", label: "Active"}, {value: "false", label: "Inactive"},
]};

const definitions = {
  terms: {label: "Terms", item: "term", id: "term_id", display: "name", search: true,
    fields: [text("name", "Term name", 50), {key: "start_date", label: "Start date", props: {type: "date"}},
      {key: "end_date", label: "End date", props: {type: "date"}},
      {key: "status", label: "Status", options: selectOptions(["Planned", "Active", "Closed"])}],
    defaults: {status: "Planned"}},
  departments: {label: "Departments", item: "department", id: "department_id", display: "name", search: true,
    fields: [text("code", "Department code", 10), text("name", "Department name", 100)]},
  courses: {label: "Courses", item: "course", id: "course_id", display: "course_code", search: true,
    fields: [text("course_code", "Course code", 15), text("title", "Course title", 150),
      ref("department_id", "Department", "departments"), number("credit_hours", "Credit hours", 0),
      number("lecture_hours", "Weekly lecture hours", 0), number("lab_hours", "Weekly lab hours", 0), status],
    defaults: {lecture_hours: 0, lab_hours: 0}},
  instructors: {label: "Instructors", item: "instructor", id: "instructor_id", display: "full_name", search: true,
    fields: [text("full_name", "Instructor name", 100), {key: "email", label: "Email", props: {type: "email", maxLength: 120}},
      ref("department_id", "Department", "departments"), number("max_daily_hours", "Maximum daily hours"),
      number("max_weekly_hours", "Maximum weekly hours"), status],
    defaults: {max_daily_hours: 4, max_weekly_hours: 18}},
  rooms: {label: "Rooms", item: "room", id: "room_id", display: "room_code", search: true,
    fields: [text("room_code", "Room code", 20), text("building", "Building", 50), number("capacity", "Capacity"),
      {key: "room_type", label: "Room type", options: selectOptions(["Lecture", "Lab", "Exam Hall"])}, status],
    defaults: {room_type: "Lecture"}},
  batches: {label: "Batches", item: "batch", id: "batch_id", display: "program_code", search: true,
    fields: [text("program_code", "Programme code", 10), number("batch_year", "Year", 1900, 9999),
      text("section", "Section", 5), number("strength", "Student count"), ref("department_id", "Department", "departments"), status]},
  offerings: {label: "Offerings", item: "offering", id: "offering_id", display: "course_id", term: true,
    fields: [ref("term_id", "Term", "terms"), ref("course_id", "Course", "courses"),
      ref("batch_id", "Batch", "batches"), ref("instructor_id", "Instructor", "instructors"),
      number("enrolled_count", "Enrolled count")]},
  enrollments: {label: "Enrollments", item: "enrollment", id: "enrollment_id", display: "offering_id", term: true,
    fields: [ref("offering_id", "Offering", "course_offerings"), ref("student_id", "Student", "students")]},
};

export function useResource(path, revision = 0) {
  const [state, setState] = useState({data: null, error: null});
  useEffect(() => {
    if (!path) {
      setState({data: null, error: null});
      return;
    }
    const controller = new AbortController();
    setState({data: null, error: null});
    request(path, {signal: controller.signal})
      .then((data) => setState({data, error: null}))
      .catch((error) => { if (error.name !== "AbortError") setState({data: null, error}); });
    return () => controller.abort();
  }, [path, revision]);
  return state;
}

function readable(type, item, references) {
  switch (type) {
    case "terms": return item.name + " · " + item.status;
    case "departments": return item.name;
    case "courses": return item.course_code + " · " + item.title;
    case "instructors": return item.full_name;
    case "rooms": return item.room_code;
    case "students": return item.full_name + " · " + item.username;
    case "batches": return [item.program_code, item.batch_year, item.section].join(" ");
    case "course_offerings":
      return lookup("courses", item.course_id, references) + " · " + lookup("batches", item.batch_id, references);
    case "enrollments": return lookup("students", item.student_id, references);
    default: return "";
  }
}

function lookup(type, value, references) {
  const id = type === "course_offerings" ? "offering_id" : type === "students" ? "user_id" : definitions[type].id;
  const found = references[type]?.find((row) => row[id] === Number(value));
  return found ? readable(type, found, references) : String(value ?? "");
}

function optionsFor(type, references, selected) {
  const id = type === "course_offerings" ? "offering_id" : type === "students" ? "user_id" : definitions[type].id;
  return [{value: "", label: "Select a record"}, ...(references[type] || [])
    .filter((row) => (row.is_active !== false && row.status !== "Closed") || row[id] === Number(selected))
    .map((row) => ({value: row[id], label: readable(type, row, references)}))];
}

function Details({definition, row, references}) {
  return <dl className="record-details">{definition.fields.map((field) => {
    let value = row[field.key];
    if (field.ref) value = lookup(field.ref, value, references);
    else if (field.props?.type === "date") value = displayDate(value);
    else if (typeof value === "boolean") value = value ? "Active" : "Inactive";
    return <div key={field.key}><dt>{field.label}</dt><dd>{value}</dd></div>;
  })}</dl>;
}

export function MasterData({section, user, notify}) {
  const editable = user.role === "Coordinator";
  const definition = definitions[section];
  const [revision, refresh] = useState(0);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("");
  const [page, setPage] = useState(1);
  const [selectedTerm, selectTerm] = useState("");
  const [editor, setEditor] = useState(null);
  const {data: references, error: referenceError} = useResource("/api/master/references", revision);
  const defaultTerm = references?.terms.find((term) => term.status === "Active") || references?.terms[0];
  const termId = selectedTerm || defaultTerm?.term_id || "";
  const params = new URLSearchParams({search, page});
  if (sort) params.set("sort", sort);
  if (definition?.term && termId) params.set("term_id", termId);
  const {data, error} = useResource(definition ? "/" + section + "?" + params : null, revision);

  function done(message) {
    setEditor(null);
    refresh((previous) => previous + 1);
    notify(message);
  }
  return <>
    <div className="page-heading"><h1>Master data</h1></div>
    <nav className="section-nav" aria-label="Master data">
      {Object.entries(definitions).map(([key, item]) => <a key={key} href={"#master/" + key}
        aria-current={section === key ? "page" : undefined}>{item.label}</a>)}
      <a href="#master/grid" aria-current={section === "grid" ? "page" : undefined}>Weekly grid</a>
    </nav>
    <ErrorSummary error={referenceError || error} />
    {!references && !referenceError && <p role="status">Loading records…</p>}
    {references && section === "grid" && <section className="panel">
      <h2>Weekly grid</h2>
      <TermSelect termId={termId} selectTerm={selectTerm} references={references} />
      {termId ? <GridEditor key={termId} termId={termId} editable={editable &&
        references.terms.find((term) => term.term_id === Number(termId))?.status !== "Closed"} notify={notify} />
        : <p>Add an academic term to set its teaching days and hours.</p>}
    </section>}
    {references && data && definition && !editor && <section className="panel">
      <div className="section-heading"><h2>{definition.label}</h2>
        {editable && <button className="primary" onClick={() => setEditor({})}>Add {definition.item}</button>}
      </div>
      {definition.term && <TermSelect termId={termId} selectTerm={(value) => { selectTerm(value); setPage(1); }} references={references} />}
      {definition.search && <form className="filter" onSubmit={(event) => {
        event.preventDefault();
        setPage(1);
        setSearch(query);
      }}>
        <Field name="search" label={"Search " + definition.label.toLowerCase()} values={{search: query}}
          change={(_, value) => setQuery(value)} maxLength={150} />
        <Field name="sort" label="Sort by" values={{sort}} change={(_, value) => { setSort(value); setPage(1); }}
          options={[{value: "", label: "Default"}, ...definition.fields.filter((field) => !field.ref && field.key !== "is_active")
            .map((field) => ({value: field.key, label: field.label}))]} />
        <button className="secondary">Search</button>
      </form>}
      {data.items.length === 0 && <p>No {definition.label.toLowerCase()} to display.</p>}
      {data.items.map((row) => <article className="master-row" key={row[definition.id]}
        aria-label={readable(section === "offerings" ? "course_offerings" : section, row, references)}>
        <Details definition={definition} row={row} references={references} />
        {editable && <button className="text-button" onClick={() => setEditor(row)}>
          {section === "enrollments" ? "Remove" : "Edit"}
        </button>}
      </article>)}
      {data.total > 25 && <div className="pager">
        <button className="secondary" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
        <span>Page {page} of {Math.ceil(data.total / 25)}</span>
        <button className="secondary" disabled={page * 25 >= data.total} onClick={() => setPage(page + 1)}>Next</button>
      </div>}
    </section>}
    {references && editor && <RecordEditor section={section} definition={definition} row={editor} termId={termId}
      references={references} done={done} cancel={() => setEditor(null)} />}
  </>;
}

function RecordEditor({section, definition, row, termId, references, done, cancel}) {
  const key = row[definition.id];
  const removing = section === "enrollments" && key;
  const action = removing ? "Remove enrollment" : key ? "Save " + definition.item : "Create " + definition.item;
  const form = useForm({
    is_active: true, ...definition.defaults, ...(definition.term && {term_id: termId}), ...row,
  }, async (values) => {
    const body = Object.fromEntries(definition.fields.map((field) => [field.key, values[field.key]]));
    if (section === "terms" && values.status === "Closed") {
      body.confirm_close = !!values.confirm_close;
      body.successor_id = Number(values.successor_id) || null;
    }
    if (row.is_active && values.is_active === "false") body.confirm_deactivate = !!values.confirm_deactivate;
    await request("/" + section + (key ? "/" + key : ""), {
      method: removing ? "DELETE" : key ? "PUT" : "POST",
      body: removing ? undefined : body,
    });
    done(removing ? "Enrollment removed." : "Record saved.");
  });
  return <form className="panel editor" onSubmit={form.handle}>
    <h2>{removing ? "Remove enrollment" : (key ? "Edit " : "Add ") + definition.item}</h2>
    <ErrorSummary error={form.error} />
    {removing ? <p>Remove the student’s link to this offering?</p> : <div className="form-grid">
      {definition.fields.map((field) => <Field {...form} key={field.key} name={field.key} label={field.label}
        required {...field.props} options={field.ref ? optionsFor(field.ref, references, form.values[field.key]) : field.options} />)}
    </div>}
    {section === "terms" && form.values.status === "Active" && <p>Activating this term moves the previous active term to Planned.</p>}
    {row.is_active && form.values.is_active === "false" && <label className="notice">
      <input type="checkbox" required checked={!!form.values.confirm_deactivate}
        onChange={(event) => form.change("confirm_deactivate", event.target.checked)} /> Deactivate this record. New offerings and runs may need a replacement.
    </label>}
    {section === "terms" && form.values.status === "Closed" && key && <>
      {row.status === "Active" && references.terms.some((term) => term.status === "Planned") &&
        <Field {...form} name="successor_id" label="Next active term" required options={[
          {value: "", label: "Select a term"}, ...references.terms.filter((term) => term.status === "Planned")
            .map((term) => ({value: term.term_id, label: term.name})),
        ]} />}
      <label className="notice"><input type="checkbox" required checked={!!form.values.confirm_close}
        onChange={(event) => form.change("confirm_close", event.target.checked)} /> Close this term and archive its published schedules.</label>
    </>}
    <FormActions action={action} busy={form.busy} cancel={cancel} />
  </form>;
}

function TermSelect({termId, selectTerm, references}) {
  if (!references.terms.length) return null;
  return <div className="term-select">
    <Field name="term_id" label="Academic term" values={{term_id: termId}} change={(_, value) => selectTerm(value)}
      options={references.terms.map((term) => ({value: term.term_id, label: readable("terms", term, references)}))} />
  </div>;
}

function gridDefaults(slots) {
  if (!slots.length) return {days: [1, 2, 3, 4, 5, 6], first_start: "08:00", slot_minutes: 60, slots_per_day: 8};
  const first = slots[0];
  const minutes = (value) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));
  return {days: [...new Set(slots.map((row) => row.day_of_week))], first_start: first.start_time.slice(0, 5),
    slot_minutes: minutes(first.end_time) - minutes(first.start_time),
    slots_per_day: slots.filter((row) => row.day_of_week === first.day_of_week).length};
}

function GridEditor({termId, editable, notify}) {
  const [revision, refresh] = useState(0);
  const [blocking, setBlocking] = useState(null);
  const {data: slots, error} = useResource("/terms/" + termId + "/grid", revision);
  function changed(message) {
    setBlocking(null);
    refresh((previous) => previous + 1);
    notify(message);
  }
  return <>
    <ErrorSummary error={error} />
    {!slots && !error && <p role="status">Loading weekly grid…</p>}
    {slots && editable && !blocking && <GridForm termId={termId} slots={slots} done={changed} />}
    {blocking && <BlockForm slot={blocking} done={changed} cancel={() => setBlocking(null)} />}
    {slots && !blocking && <SlotList slots={slots} action={editable ? (slot) => setBlocking(slot) : undefined}
      label={(slot) => slot.is_blocked ? "Edit blocked slot" : "Block slot"} />}
  </>;
}

function GridForm({termId, slots, done}) {
  const form = useForm(gridDefaults(slots), async (values) => {
    await request("/terms/" + termId + "/grid", {method: "PUT", body: values});
    done("Weekly grid saved.");
  });
  return <form className="grid-form" onSubmit={form.handle}>
    <ErrorSummary error={form.error} />
    <fieldset><legend>Teaching days</legend><div className="weekdays">
      {weekdays.map((day, index) => {
        const value = index + 1;
        const checked = form.values.days.includes(value);
        return <label key={day}><input type="checkbox" checked={checked} onChange={() =>
          form.change("days", checked ? form.values.days.filter((item) => item !== value) : [...form.values.days, value])} /> {day}</label>;
      })}
    </div></fieldset>
    <div className="form-grid">
      <Field {...form} name="first_start" label="First start time" required type="time" />
      <Field {...form} name="slot_minutes" label="Minutes per slot" required type="number" min={5} max={240} />
      <Field {...form} name="slots_per_day" label="Slots per day" required type="number" min={1} max={48} />
    </div>
    <FormActions action="Save weekly grid" busy={form.busy} />
  </form>;
}

function BlockForm({slot, done, cancel}) {
  const form = useForm({is_blocked: "true", block_reason: slot.block_reason || ""}, async (values) => {
    await request("/slots/" + slot.slot_id + "/block", {method: "PUT", body: values});
    done(values.is_blocked === "true" ? "Slot blocked." : "Slot unblocked.");
  });
  return <form className="grid-form" onSubmit={form.handle}>
    <h3>{weekdays[slot.day_of_week - 1]} · {slot.start_time.slice(0, 5)}</h3>
    <ErrorSummary error={form.error} />
    <Field {...form} name="is_blocked" label="Slot status" options={[{value: "true", label: "Blocked"}, {value: "false", label: "Open"}]} />
    {form.values.is_blocked === "true" && <Field {...form} name="block_reason" label="Block reason" required maxLength={50} />}
    <FormActions action="Save slot" busy={form.busy} cancel={cancel} />
  </form>;
}

function SlotList({slots, action, label, busy}) {
  if (!slots.length) return <p>No weekly slots have been configured.</p>;
  return <div className="slot-list">{slots.map((slot) => <article className="slot-row" key={slot.slot_id}
    aria-label={weekdays[slot.day_of_week - 1] + " " + slot.start_time.slice(0, 5)}>
    <strong>{weekdays[slot.day_of_week - 1]}</strong>
    <span>{slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}</span>
    <span>{slot.is_blocked ? "Blocked · " + slot.block_reason : slot.is_available === false ? "Unavailable" : "Available"}</span>
    {action && <button className="text-button" disabled={busy} onClick={() => action(slot)}>{label(slot)}</button>}
  </article>)}</div>;
}

export function Availability({user, notify}) {
  const {data: references, error} = useResource("/api/master/references");
  const [term, setTerm] = useState("");
  const [instructor, setInstructor] = useState("");
  const [revision, refresh] = useState(0);
  const [changeError, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const termId = term || (references?.terms.find((term) => term.status === "Active") || references?.terms[0])?.term_id;
  const instructorId = user.instructor_id || instructor || references?.instructors?.[0]?.instructor_id;
  const query = "?instructor_id=" + instructorId;
  const {data: slots, error: slotsError} = useResource(termId && instructorId ? "/availability/" + termId + query : null, revision);

  async function toggle(slot) {
    setError(null);
    setSaving(true);
    try {
      await request("/availability/slots/" + slot.slot_id + query, {method: "PUT", body: {is_available: !slot.is_available}});
      refresh((previous) => previous + 1);
      notify("Availability saved. Regenerate any existing draft to apply the change.");
    } catch (failure) {
      setError(failure);
    } finally {
      setSaving(false);
    }
  }
  return <>
    <div className="page-heading"><div><h1>Availability</h1>
      <p>Mark teaching slots as unavailable for future timetable runs.</p></div></div>
    <section className="panel">
      <ErrorSummary error={error || slotsError || changeError} />
      {references && <div className="form-grid">
        <TermSelect termId={termId} selectTerm={setTerm} references={references} />
        {user.role === "Coordinator" && <div className="term-select">
          <Field name="instructor_id" label="Instructor" values={{instructor_id: instructorId}}
            change={(_, value) => setInstructor(value)} options={optionsFor("instructors", references, instructorId)} />
        </div>}
      </div>}
      {references && !termId && <p>No academic term is available.</p>}
      {references && termId && !instructorId && <p>Add an instructor in Master data to set availability.</p>}
      {slots && <SlotList slots={slots} busy={saving} action={
        references?.terms.find((term) => term.term_id === Number(termId))?.status === "Closed" ? undefined : toggle
      } label={(slot) => slot.is_available ? "Mark unavailable" : "Mark available"} />}
    </section>
  </>;
}

