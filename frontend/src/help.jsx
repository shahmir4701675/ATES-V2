const guides = {
  dashboard: ["Dashboard", "Create and activate a term before generating. The term summary shows the teaching records already available."],
  users: ["User accounts", "Link Faculty to an instructor and Students to a batch. Deactivation ends sessions and keeps the account’s audit history."],
  availability: ["Availability", "Unmarked teaching slots are available by default. Changing availability applies to future generation runs."],
  generate: ["Generation", "Use the Default configuration unless your department needs a specific rule or time limit. If readiness fails, open the conflict report and correct the listed input."],
  import: ["CSV import", "Download the template for your record type. Save it as UTF-8 and keep its headers. Preview the file to see line-level errors before adding records."],
  settings: ["Settings", "Create dated exam sessions before running the exam scheduler. Soft weights range from 0 to 10. You must confirm disabling a non-mandatory hard rule."],
  master: ["Master data", "Add the term and weekly grid, then the departments, courses, instructors, batches, rooms and offerings. Mark breaks with a short reason."],
  schedules: ["Versions", "Only a Coordinator can edit a Generated version. An Approver reviews and publishes it. Publishing a replacement archives the previous version."],
  timetable: ["Timetable", "Use the filters to find a class. Coordinators can drag a class to a slot or use Adjust schedule with a keyboard or touch. A lab moves as one block."],
  exams: ["Exams", "Filter the list by date, batch, course or room. An exam can use multiple rooms. The seat count is shown beside each room."],
  password: ["Password", "Use at least eight characters. Changing the password ends the current session and any other active sessions for the account."],
  audit: ["Audit log", "Filter by actor username, action code or a time window using Asia/Karachi time."],
};

export function Help({previous}) {
  const category = previous.split("/")[0];
  const [title, body] = guides[category] || guides.schedules;
  return <>
    <div className="page-heading"><h1>Help</h1></div>
    <section className="panel editor">
      <h2>{title}</h2>
      <p>{body}</p>
      <a href={"#" + previous}>Back to {title.toLowerCase()}</a>
    </section>
  </>;
}

