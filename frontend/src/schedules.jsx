import {useEffect, useRef, useState} from "react";
import {downloadFile, request} from "./api";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";
import {useResource, weekdays} from "./master";
import {Adjustments, Review, useScheduleChanges} from "./versions";

const Status = ({value}) => <span className="status-tag">{value}</span>;
const option = (value, label) => ({value, label});

export function Generate({exam = false}) {
  const {data: references, error} = useResource("/api/master/references");
  const terms = references?.terms.filter((term) => term.status !== "Closed") || [];
  const initial = (terms.find((term) => term.status === "Active") || terms[0])?.term_id;
  return <>
    <div className="page-heading"><div><h1>{exam ? "Generate exam schedule" : "Generate timetable"}</h1>
      <p>Create a schedule version for an academic term.</p></div></div>
    <ErrorSummary error={error} />
    {!references && !error && <p role="status">Loading terms…</p>}
    {references && !initial && <section className="panel"><p>Create an academic term before generating.</p>
      <a href="#master/terms">Open academic terms</a></section>}
    {initial && <GenerateForm terms={terms} initial={initial} exam={exam} />}
  </>;
}

function GenerateForm({terms, initial, exam}) {
  const kind = exam ? "Exam" : "Timetable";
  const attempt = useRef(null);
  const form = useForm({term_id: initial}, async ({term_id, source_id, config_id}) => {
    const fingerprint = [term_id, source_id || "", config_id || ""].join("/");
    if (attempt.current?.fingerprint !== fingerprint) {
      attempt.current = {fingerprint, id: crypto.randomUUID()};
    }
    const result = await request("/schedules/generate", {method: "POST", body: {
      term_id: Number(term_id), source_id: Number(source_id) || null, config_id: Number(config_id) || null,
      request_token: attempt.current.id, schedule_type: kind,
    }});
    attempt.current = null;
    location.hash = "schedules/" + result.schedule_id;
  });
  const {data: versions, error} = useResource("/schedules?term_id=" + form.values.term_id + "&schedule_type=" + kind);
  const {data: configs, error: configError} = useResource("/configs?schedule_type=" + kind + "&term_id=" + form.values.term_id);
  return <form className="panel editor" onSubmit={form.handle}>
    <ErrorSummary error={form.error || error || configError} />
    <Field {...form} name="term_id" label="Academic term" required options={terms.map((term) => option(term.term_id, term.name))}
      change={(name, value) => { form.change(name, value); form.change("source_id", ""); form.change("config_id", ""); }} />
    <Field {...form} name="config_id" label="Configuration"
      options={[option("", "Default"), ...(configs || []).filter((item) => item.name !== "Default")
        .map((item) => option(item.config_id, item.name))]} />
    {!!versions?.some((version) => ["Generated", "Published", "Archived"].includes(version.status)) &&
      <Field {...form} name="source_id" label="Previous version" hint="Preserve locks from the selected version."
        options={[option("", "None"), ...versions.filter((version) => ["Generated", "Published", "Archived"].includes(version.status))
          .map((version) => option(version.schedule_id, "Version " + version.version_no + " · " + version.status))]} />}
    <FormActions action="Generate" busy={form.busy} cancel={() => { location.hash = "dashboard"; }} />
  </form>;
}

export function Versions({user, exam = false}) {
  const {data: references, error: termsError} = useResource("/api/master/references");
  const [selected, setTerm] = useState("");
  const termId = selected || (references?.terms.find((term) => term.status === "Active") || references?.terms[0])?.term_id;
  const {data, error} = useResource(termId ? "/schedules?term_id=" + termId + "&schedule_type=" + (exam ? "Exam" : "Timetable") : null);
  return <>
    <div className="page-heading"><h1>{exam ? "Exam schedule versions" : "Timetable versions"}</h1>
      {user.role === "Coordinator" && <a className="primary" href={exam ? "#generate-exams" : "#generate"}>
        {exam ? "Generate exam schedule" : "Generate timetable"}</a>}
    </div>
    <section className="panel">
      <ErrorSummary error={error || termsError} />
      {!!references?.terms.length && <div className="term-select">
        <Field name="term_id" label="Academic term" values={{term_id: termId}} change={(_, value) => setTerm(value)}
          options={references.terms.map((term) => option(term.term_id, term.name))} />
      </div>}
      {references && !references.terms.length && <p>No academic terms have been added.</p>}
      {data?.length === 0 && <p>This term has no {exam ? "exam schedule" : "timetable"} versions.</p>}
      {data?.map((version) => <div className="version-row" key={version.schedule_id}>
        <div><strong>Version {version.version_no}</strong> <Status value={version.status} />
          {version.outcome && <p>{version.outcome}</p>}</div>
        <a className="secondary" href={"#schedules/" + version.schedule_id}>Open version</a>
      </div>)}
    </section>
  </>;
}

export function RunView({id, user}) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let timer;
    const controller = new AbortController();
    async function poll() {
      try {
        const current = await request("/schedules/" + id + "/status", {signal: controller.signal});
        setData(current);
        if (current.status === "Generating") timer = setTimeout(poll, 2000);
      } catch (failure) {
        if (failure.name !== "AbortError") setError(failure);
      }
    }
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [id]);

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      const response = await request("/schedules/" + id + "/cancel", {method: "POST"});
      setData(response);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  async function versionAction(action) {
    setBusy(true);
    setError(null);
    try {
      const next = await request("/schedules/" + id + "/" + action, {method: "POST", body: {revision: data.revision}});
      if (action === "duplicate") location.hash = "schedules/" + next.schedule_id;
      else setData(next);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }

  const hasEntries = ["Generated", "Published", "Archived"].includes(data?.status);
  const exam = data?.schedule_type === "Exam";
  return <>
    <div className="page-heading"><div>
      <a href={exam ? "#exam-versions" : "#versions"}>{exam ? "Exam schedule versions" : "Timetable versions"}</a>
      <h1>{data ? (exam ? "Exam schedule" : "Timetable") + " version " + data.version_no : "Schedule version"}</h1>
      {data && <p>{data.term_name} <Status value={data.status} /></p>}
    </div></div>
    <ErrorSummary error={error} />
    {!data && !error && <p role="status">Loading version…</p>}
    {data && <section className="panel run-panel">
      {data.status === "Generating" && <>
        <p role="status">{data.phase} · {Math.floor(data.elapsed)} seconds elapsed</p>
        <progress className="run-progress" aria-label="Schedule generation in progress" />
        {user.role === "Coordinator" && <button className="secondary" disabled={busy} onClick={cancel}>Cancel generation</button>}
      </>}
      {data.outcome && <p role="status">{data.outcome}</p>}
      {hasEntries && <dl className="term-counts">
        <div><dt>Solver result</dt><dd>{data.solver_status}</dd></div>
        <div><dt>Objective score</dt><dd>{data.objective_score}</dd></div>
        <div><dt>Run time</dt><dd>{Number(data.run_seconds).toFixed(2)} s</dd></div>
        {exam && data.statistics && <>
          <div><dt>Exams</dt><dd>{data.statistics.courses}</dd></div>
          <div><dt>Sessions used</dt><dd>{data.statistics.sessions_used}</dd></div>
          <div><dt>Rooms used</dt><dd>{data.statistics.rooms_used}</dd></div>
        </>}
      </dl>}
      {hasEntries && <a className="primary" href={(exam ? "#exams/" : "#timetable/") + id}>
        {exam ? "View exam schedule" : "View timetable"}</a>}
      {user.role === "Coordinator" && hasEntries && <button className="secondary" disabled={busy}
        onClick={() => versionAction("duplicate")}>Duplicate to Draft</button>}
      {user.role === "Coordinator" && data.has_copy && <button className="primary" disabled={busy}
        onClick={() => versionAction("validate-draft")}>Validate draft</button>}
      {["Draft", "Infeasible"].includes(data.status) && <ConflictList id={id} />}
    </section>}
    {user.role === "Approver" && data?.status === "Generated" && <div className="adjustment">
      <Review id={id} complete={setData} /></div>}
  </>;
}

function activeFilters(filters) {
  return new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
}

function ExportActions({id, version, filters, user}) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  async function download(format, group) {
    setBusy(true);
    setError(null);
    try {
      const query = group ? new URLSearchParams({group_by: group}) : activeFilters(filters);
      query.set("format", format);
      await downloadFile("/schedules/" + id + "/export?" + query,
        "ates-" + version.schedule_type.toLowerCase() + "-v" + version.version_no + "." + format);
    } catch (failure) {
      setError(failure);
    } finally {
      setBusy(false);
    }
  }
  return <>
    <ErrorSummary error={error} />
    <div className="form-actions exports">
      <button className="secondary" disabled={busy} onClick={() => download("pdf")}>Export PDF</button>
      <button className="secondary" disabled={busy} onClick={() => download("csv")}>Export CSV</button>
      {user.role === "Coordinator" && <>
        <button className="secondary" disabled={busy} onClick={() => download("pdf", "batch")}>PDF by batch</button>
        <button className="secondary" disabled={busy} onClick={() => download("pdf", "instructor")}>PDF by instructor</button>
      </>}
    </div>
  </>;
}

export function ExamView({id, user, reader}) {
  const [revision, reload] = useState(0);
  const {data, error} = useResource("/schedules/" + id + "/entries", revision);
  const {data: version, error: versionError} = useResource("/schedules/" + id + "/status", revision);
  const operations = useScheduleChanges(id, version, () => reload((prior) => prior + 1));
  const editable = user.role === "Coordinator" && version?.status === "Generated";
  const [filters, setFilters] = useState({});
  const query = activeFilters(filters).toString();
  const filtered = useResource(query ? "/schedules/" + id + "/entries?" + query : null, revision);
  const change = (field, value) => setFilters((previous) => ({...previous, [field]: value}));
  return <>
    <div className="page-heading"><div>{!reader && <a href={"#schedules/" + id}>Version summary</a>}<h1>Exam schedule</h1>
      {version && <p>{version.term_name} · Version {version.version_no} <Status value={version.status} /></p>}</div></div>
    <ErrorSummary error={error || versionError || filtered.error} />
    {data && <ExamList data={data} visible={query ? filtered.data?.entries : data.entries} filters={filters}
      change={change} drag={editable ? operations : null} />}
    {data && version && <ExportActions id={id} version={version} filters={filters} user={user} />}
    {data && editable && <Adjustments data={data} exam operations={operations} />}
    {!data && !error && <p role="status">Loading exam schedule…</p>}
  </>;
}

function ExamList({data, filters, change, drag, visible}) {
  const courses = new Map(data.courses.map((item) => [item.course_id, item]));
  const slots = new Map(data.exam_slots.map((item) => [item.exam_slot_id, item]));
  const rooms = new Map(data.rooms.map((item) => [item.room_id, item]));
  const batches = Object.assign({}, ...data.courses.map((item) => item.batches));
  const dates = [...new Set(data.exam_slots.map((slot) => slot.exam_date))];
  const dateLabel = (value) => value.split("-").reverse().join("/");
  const choices = (values) => [option("", "All"), ...values];
  const entries = visible || [];
  return <section className="panel">
    <div className="timetable-filters">
      <Field name="course" label="Course" values={filters} change={change}
        options={choices(data.courses.map((item) => option(item.course_id, item.course_code)))} />
      <Field name="date" label="Date" values={filters} change={change}
        options={choices(dates.map((date) => option(date, dateLabel(date))))} />
      <Field name="batch" label="Batch" values={filters} change={change}
        options={choices(Object.entries(batches).map(([key, label]) => option(key, label)))} />
      <Field name="room" label="Room" values={filters} change={change}
        options={choices(data.rooms.map((item) => option(item.room_id, item.room_code)))} />
    </div>
    <p className="timetable-count" role="status">{visible ? entries.length + (entries.length === 1 ? " exam" : " exams")
      : "Loading filtered exams…"}</p>
    {entries.map((item) => {
      const course = courses.get(item.course);
      const slot = slots.get(item.slot);
      return <article className="version-row" key={item.course} aria-label={course.course_code}
        draggable={!!drag && !item.is_locked} onDragStart={(event) => event.dataTransfer.setData("application/x-ates-exam", String(item.course))}>
        <div><h2>{course.course_code} · {course.title}</h2>
          <p>{dateLabel(slot.exam_date)} · {slot.start_time.slice(0, 5)}–{slot.end_time.slice(0, 5)}</p>
          <p>{Object.values(course.batches).join(" · ")} · {item.student_count} candidates</p></div>
        <ul>{Object.entries(item.rooms).map(([key, seats]) => <li key={key}>
          {rooms.get(Number(key)).room_code} · {seats} seats</li>)}
          {item.is_locked && <li>Locked</li>}{item.is_manual_override && <li>Manual override</li>}</ul>
      </article>;
    })}
    {drag && <div className="exam-targets" aria-label="Exam move destinations">
      {data.exam_slots.map((slot) => <div key={slot.exam_slot_id} className="drop-target"
        onDragOver={(event) => event.preventDefault()} onDrop={(event) => {
          event.preventDefault();
          const entry = event.dataTransfer.getData("application/x-ates-exam");
          if (entry) drag.change("entries", "PUT", {entry, slot_id: slot.exam_slot_id}, "Exam moved.");
        }}>{dateLabel(slot.exam_date)} · {slot.start_time.slice(0, 5)}</div>)}
    </div>}
  </section>;
}

function ConflictList({id}) {
  const {data, error} = useResource("/schedules/" + id + "/conflicts");
  const [filter, setFilter] = useState("");
  const [downloadError, setError] = useState(null);
  const rows = data?.filter((row) => !filter || row.conflict_type === filter);
  async function download() {
    setError(null);
    try {
      const query = new URLSearchParams({format: "csv"});
      if (filter) query.set("conflict_type", filter);
      await downloadFile("/schedules/" + id + "/conflicts?" + query, "ates-conflicts-" + id + ".csv");
    } catch (failure) {
      setError(failure);
    }
  }
  return <div className="conflicts">
    <div className="section-heading"><h2>Conflict report</h2>
      {!!data?.length && <button className="secondary" onClick={download}>Download conflict CSV</button>}
    </div>
    <ErrorSummary error={error || downloadError} />
    {!!data?.length && <div className="term-select">
      <Field name="conflict_type" label="Conflict type" values={{conflict_type: filter}} change={(_, value) => setFilter(value)}
        options={[option("", "All types"), ...[...new Set(data.map((row) => row.conflict_type))]
          .map((value) => option(value, value))]} /></div>}
    <ul>{rows?.map((item) => <li key={item.conflict_id}><strong>{item.conflict_type}</strong>
      {item.entity_ref && <span> · {item.entity_ref}</span>}<p>{item.description}</p></li>)}</ul>
  </div>;
}

export function TimetableView({id, user, reader}) {
  const [revision, reload] = useState(0);
  const {data, error} = useResource("/schedules/" + id + "/entries", revision);
  const {data: version, error: versionError} = useResource("/schedules/" + id + "/status", revision);
  const operations = useScheduleChanges(id, version, () => reload((prior) => prior + 1));
  const editable = user.role === "Coordinator" && version?.status === "Generated";
  const [filters, setFilters] = useState({});
  const query = activeFilters(filters).toString();
  const filtered = useResource(query ? "/schedules/" + id + "/entries?" + query : null, revision);
  const change = (field, value) => setFilters((previous) => ({...previous, [field]: value}));
  return <>
    <div className="page-heading"><div>{!reader && <a href={"#schedules/" + id}>Version summary</a>}<h1>Weekly timetable</h1>
      {version && <p>{version.term_name} · Version {version.version_no} <Status value={version.status} /></p>}</div></div>
    <ErrorSummary error={error || versionError || filtered.error} />
    {!data && !error && <p role="status">Loading timetable…</p>}
    {data && <Grid data={data} visible={query ? filtered.data?.entries : data.entries} filters={filters}
      change={change} drag={editable ? operations : null} />}
    {data && version && <ExportActions id={id} version={version} filters={filters} user={user} />}
    {data && editable && <Adjustments data={data} operations={operations} />}
  </>;
}

function Grid({data, filters, change, drag, visible}) {
  const items = new Map(data.offerings.map((row) => [row.offering_id, row]));
  const rooms = new Map(data.rooms.map((row) => [row.room_id, row]));
  const batches = new Map(data.offerings.map((row) => [row.batch_id, [row.program_code, row.batch_year, row.section].join(" ")]));
  const teachers = new Map(data.offerings.map((row) => [row.instructor_id, row.full_name]));
  const slotEntries = new Map();
  const entries = visible || [];
  for (const entry of entries) {
    for (const slot of entry.slots) {
      if (!slotEntries.has(slot)) slotEntries.set(slot, []);
      slotEntries.get(slot).push(entry);
    }
  }
  const allDays = [...new Set(data.slots.map((row) => row.day_of_week))];
  const firstWeekday = data.first_weekday || 1;
  allDays.sort((left, right) => (left - firstWeekday + 7) % 7 - (right - firstWeekday + 7) % 7);
  const days = filters.day ? [Number(filters.day)] : allDays;
  const slotIndexes = [...new Set(data.slots.map((row) => row.slot_index))].sort((left, right) => left - right);
  const slotFor = new Map(data.slots.map((row) => [row.day_of_week + ":" + row.slot_index, row]));
  const choices = (map) => [option("", "All"), ...Array.from(map, ([key, value]) => option(key, value))];
  return <section className="panel timetable-panel">
    <div className="timetable-filters">
      <Field name="batch" label="Batch" values={filters} change={change} options={choices(batches)} />
      <Field name="instructor" label="Instructor" values={filters} change={change} options={choices(teachers)} />
      <Field name="room" label="Room" values={filters} change={change}
        options={choices(new Map(Array.from(rooms, ([key, room]) => [key, room.room_code])))} />
      <Field name="course" label="Course" values={filters} change={change}
        options={choices(new Map(data.offerings.map((item) => [item.course_id, item.course_code])))} />
      <Field name="day" label="Day" values={filters} change={change}
        options={choices(new Map(allDays.map((day) => [day, weekdays[day - 1]])))} />
    </div>
    <p className="timetable-count" role="status">{visible ? entries.length + (entries.length === 1 ? " session" : " sessions")
      : "Loading filtered sessions…"}</p>
    <div className="table-scroll" tabIndex={0} aria-label="Weekly timetable grid">
      <table className="weekly-table">
        <thead><tr><th scope="col">Time</th>{days.map((day) => <th scope="col" key={day}>{weekdays[day - 1]}</th>)}</tr></thead>
        <tbody>{slotIndexes.map((index) => {
          const interval = allDays.map((day) => slotFor.get(day + ":" + index)).find(Boolean);
          return <tr key={index}><th scope="row">{interval.start_time.slice(0, 5)}–{interval.end_time.slice(0, 5)}</th>
            {days.map((day) => {
              const slot = slotFor.get(day + ":" + index);
              return <td key={day} className={slot?.is_blocked ? "blocked-cell" : undefined}
                onDragOver={drag && slot ? (event) => event.preventDefault() : undefined}
                onDrop={drag && slot ? (event) => {
                  event.preventDefault();
                  const entry = event.dataTransfer.getData("application/x-ates-class");
                  if (entry) drag.change("entries", "PUT", {entry, slot_id: slot.slot_id}, "Class moved.");
                } : undefined}>
                {slot?.is_blocked && <span className="block-label">{slot.block_reason}</span>}
                {slotEntries.get(slot?.slot_id)?.map((entry) => {
                  const course = items.get(entry.offering);
                  const continuation = entry.slots[0] !== slot.slot_id;
                  return <article key={entry.key} className={"session-card " + (entry.kind === "Lab" ? "lab-card" : "")}
                    draggable={!!drag && !continuation && !entry.is_locked}
                    onDragStart={(event) => event.dataTransfer.setData("application/x-ates-class", entry.key)}>
                    <strong>{course.course_code} · {entry.kind}{continuation ? " continued" : ""}</strong>
                    {!continuation && <><div>{course.title}</div><div>{course.full_name} · {rooms.get(entry.room).room_code}</div>
                      <div>{batches.get(entry.batch)}</div>
                      {entry.is_locked && <div>Locked</div>}{entry.is_manual_override && <div>Manual override</div>}</>}
                  </article>;
                })}
              </td>;
            })}
          </tr>;
        })}</tbody>
      </table>
    </div>
  </section>;
}

