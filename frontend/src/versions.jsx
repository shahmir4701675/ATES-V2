import {useState} from "react";
import {request} from "./api";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";
import {useResource, weekdays} from "./master";

export function Review({id, complete}) {
  const {data, error} = useResource("/schedules/" + id + "/review");
  return <section className="panel editor">
    <h2>Review and publish</h2>
    <ErrorSummary error={error} />
    {data ? <Approval id={id} summary={data} complete={complete} /> : !error && <p role="status">Loading review…</p>}
  </section>;
}

function Approval({id, summary, complete}) {
  const form = useForm({}, async (values) => {
    const result = await request("/schedules/" + id + "/publish", {method: "POST", body: {
      revision: summary.revision, replace_id: summary.published_id, confirmed: !!values.confirmed,
    }});
    complete(result);
  });
  return <form className="editor" onSubmit={form.handle}>
    <dl className="term-counts">
      <div><dt>Sessions or exams</dt><dd>{summary.entries}</dd></div>
      <div><dt>Objective score</dt><dd>{summary.score}</dd></div>
      <div><dt>Hard conflicts</dt><dd>{summary.issues.length}</dd></div>
    </dl>
    <ErrorSummary error={form.error} />
    {!!summary.issues.length && <ul className="conflicts">{summary.issues.map((issue, index) =>
      <li key={index}><strong>{issue.code}</strong> · {issue.message}</li>
    )}</ul>}
    <label className="notice"><input type="checkbox" required checked={!!form.values.confirmed}
      onChange={(event) => form.change("confirmed", event.target.checked)} /> {summary.published_id
        ? "Publish this schedule and archive version " + summary.published_version + "."
        : "Publish this schedule for Faculty and Students."}</label>
    <FormActions action="Publish schedule" busy={form.busy || !!summary.issues.length} />
  </form>;
}

export function useScheduleChanges(id, version, refresh) {
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  async function change(path, method, body, message) {
    if (!version || busy) return false;
    setBusy(true);
    setError(null);
    setNotice("");
    try {
      await request("/schedules/" + id + "/" + path, {method, body: {...body, revision: version.revision}});
      refresh();
      setNotice(message);
      return true;
    } catch (failure) {
      setError(failure);
      return false;
    } finally {
      setBusy(false);
    }
  }
  return {error, busy, notice, change};
}

export function Adjustments({data, exam, operations}) {
  const [entry, selectEntry] = useState("");
  const [confirmUndo, confirm] = useState(false);
  const records = data.entries;
  const id = (item) => String(exam ? item.course : item.key);
  const choice = records.find((item) => id(item) === entry);
  async function undo() {
    if (await operations.change("undo", "POST", {}, "Original assignments restored.")) confirm(false);
  }
  return <section className="panel adjustment">
    <h2>Adjust schedule</h2>
    <ErrorSummary error={operations.error} />
    {operations.notice && <p role="status" className="notice">{operations.notice}</p>}
    <Field name="entry" label={exam ? "Exam" : "Teaching session"} values={{entry}} change={(_, value) => selectEntry(value)}
      options={[{value: "", label: "Select an entry"}, ...records.map((item) => ({
        value: id(item),
        label: exam ? data.courses.find((row) => row.course_id === item.course).course_code :
          data.offerings.find((row) => row.offering_id === item.offering).course_code + " · " + item.kind + " · " + item.key.split(":").at(-1),
      }))]} />
    {choice && <MoveEntry key={entry + "_" + (exam ? choice.slot : choice.slots[0])} choice={choice} entry={entry}
      exam={exam} data={data} operations={operations} />}
    {records.some((item) => item.is_manual_override) && <div className="form-actions">
      {confirmUndo ? <><p>Restore the original solver assignments for this version?</p>
        <button className="primary" disabled={operations.busy} onClick={undo}>Confirm restore</button>
        <button className="secondary" type="button" onClick={() => confirm(false)}>Cancel</button></>
        : <button className="secondary" onClick={() => confirm(true)}>Undo manual changes</button>}
    </div>}
  </section>;
}

function MoveEntry({choice, entry, exam, data, operations}) {
  const rooms = Object.entries(choice.rooms || {});
  const [setRooms, toggleRooms] = useState(false);
  const slots = exam ? data.exam_slots : data.slots;
  const form = useForm({slot_id: exam ? choice.slot : choice.slots[0], room_id: choice.room,
    ...Object.fromEntries(rooms.map(([room, seats]) => ["seats_" + room, seats])),
  }, async (values) => {
    const body = {entry, slot_id: Number(values.slot_id)};
    if (!exam) {
      body.room_id = Number(values.room_id);
    } else if (setRooms) {
      const assigned = data.rooms.filter((room) => Number(values["seats_" + room.room_id]) > 0);
      body.seats = Object.fromEntries(assigned.map((room) => [room.room_id, Number(values["seats_" + room.room_id])]));
    }
    await operations.change("entries", "PUT", body, "Entry moved.");
  });
  return <div className="grid-form">
    <button className="secondary" disabled={operations.busy} onClick={() => operations.change("locks", "PUT",
      {entry, locked: !choice.is_locked}, choice.is_locked ? "Entry unlocked." : "Entry locked.")}>
      {choice.is_locked ? "Unlock entry" : "Lock entry"}
    </button>
    {!choice.is_locked && <form className="grid-form" onSubmit={form.handle}>
      <Field {...form} name="slot_id" label={exam ? "Destination exam session" : "Destination start slot"} options={slots.map((slot) => ({
        value: exam ? slot.exam_slot_id : slot.slot_id,
        label: (exam ? slot.exam_date.split("-").reverse().join("/") : weekdays[slot.day_of_week - 1]) +
          " · " + slot.start_time.slice(0, 5),
      }))} />
      {!exam && <Field {...form} name="room_id" label="Destination room"
        options={data.rooms.map((room) => ({value: room.room_id, label: room.room_code}))} />}
      {exam && <label><input type="checkbox" checked={setRooms} onChange={(event) => toggleRooms(event.target.checked)} /> Change allocated rooms</label>}
      {setRooms && <fieldset className="form-grid"><legend>Allocate {choice.student_count} seats</legend>
        {data.rooms.map((room) => <Field key={room.room_id} {...form} name={"seats_" + room.room_id}
          label={room.room_code + " seats"} hint={"Capacity " + room.capacity} type="number" min={0} max={room.capacity} />)}
      </fieldset>}
      <FormActions action="Move entry" busy={operations.busy || form.busy} />
    </form>}
  </div>;
}

export function Published({exam, View, user}) {
  const [term, selectTerm] = useState("");
  const {data, error} = useResource("/schedules/published?schedule_type=" + (exam ? "Exam" : "Timetable") +
    (term ? "&term_id=" + term : ""));
  return <>
    <ErrorSummary error={error} />
    {!!data?.terms.length && (data.terms.length > 1 || !data.schedule_id) && <div className="term-select">
      <Field name="term" label="Published term" values={{term: term || data.term_id}} change={(_, value) => selectTerm(value)}
        options={[{value: "", label: "Active term"}, ...data.terms.map((row) => ({value: row.term_id, label: row.name}))]} />
    </div>}
    {data?.schedule_id ? <View id={data.schedule_id} user={user} reader key={data.schedule_id} /> : <>
      <div className="page-heading"><h1>{exam ? "Published exam schedule" : "Published timetable"}</h1></div>
      {data ? <section className="panel"><p>{data.term_name ? "No schedule has been published for " + data.term_name + "." :
        "There is no active academic term."}</p></section> : !error && <p role="status">Loading published schedule…</p>}
    </>}
  </>;
}

