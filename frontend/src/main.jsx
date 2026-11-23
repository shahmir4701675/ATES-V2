import {useEffect, useState} from "react";
import {createRoot} from "react-dom/client";
import {request, setToken, token} from "./api";
import {Users} from "./accounts";
import {ErrorSummary, Field, FormActions, useForm} from "./forms";
import {Availability, MasterData, useResource} from "./master";
import {ExamView, Generate, RunView, TimetableView, Versions} from "./schedules";
import {ImportWizard} from "./imports";
import {Settings} from "./settings";
import {Published} from "./versions";
import {Audit} from "./audit";
import {Help} from "./help";
import {roleDescription} from "./text";
import "./style.css";

function Mark() {
  return <svg viewBox="0 0 42 42" width="42" height="42" aria-hidden="true">
    <rect width="42" height="42" rx="12" fill="currentColor"/>
    <path d="M12 15h18v15H12z M12 20h18 M17 12v6 M25 12v6" fill="none" stroke="white" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
    <path d="m18 25 2 2 4-4" fill="none" stroke="#b8dfad" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
  </svg>;
}

function Brand({login = false}) {
  return <div className={login ? "brand login-brand" : "brand"}><Mark /><div>
    <strong>ATES</strong><span>{login ? "Auto Timetable / Exam Scheduler" : "Academic scheduling"}</span>
  </div></div>;
}

function Login({onLogin, message}) {
  const form = useForm({}, async (values) => {
    const result = await request("/auth/login", {method: "POST", body: values});
    setToken(result.access_token);
    onLogin(result.user);
  });
  return <main className="login-layout">
    <aside className="login-cover">
      <Brand login />
      <div className="cover-content">
        <div className="cover-rule" />
        <h2>Academic<br />scheduling</h2>
        <p>Class timetables and exam schedules in one workspace.</p>
      </div>
      <div className="schedule-decoration" aria-hidden="true">
        {Array.from({length: 35}, (_, index) => <span key={index} />)}
      </div>
    </aside>
    <section className="login-content" aria-labelledby="login-title">
      <div className="login-inner">
        <div className="mobile-brand"><Brand login /></div>
        <h1 id="login-title">Sign in</h1>
        <p className="login-intro">Use the account provided by your administrator.</p>
        {message && <p className="notice" role="status">{message}</p>}
        <form onSubmit={form.handle}>
          <ErrorSummary error={form.error} />
          <Field {...form} name="username" autoComplete="username" required maxLength={40} />
          <Field {...form} name="password" autoComplete="current-password" type="password" required />
          <button className="primary sign-in" disabled={form.busy}>{form.busy ? "Signing in…" : "Sign in"}</button>
        </form>
      </div>
    </section>
  </main>;
}

function ChangePassword({done, cancel}) {
  const form = useForm({}, async (values) => {
    await request("/auth/password", {method: "PUT", body: values});
    done("Password changed. Sign in with your new password.");
  });
  return <>
    <div className="page-heading"><h1>Change password</h1></div>
    <form className="panel editor" onSubmit={form.handle}>
      <p>Changing your password ends your active sessions.</p>
      <ErrorSummary error={form.error} />
      <Field {...form} name="current_password" required type="password" autoComplete="current-password" />
      <Field {...form} name="password" label="New password" hint="Use at least 8 characters." required
        type="password" autoComplete="new-password" />
      <FormActions action="Change password" cancel={cancel} busy={form.busy} />
    </form>
  </>;
}

function ApiReference() {
  const [view, setView] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let active = true;
    Promise.all([
      request("/openapi.json"),
      import("swagger-ui-dist/swagger-ui-es-bundle.js"),
      import("swagger-ui-dist/swagger-ui.css"),
    ]).then(([schema, swagger]) => {
      if (active) setView(() => ({schema, SwaggerUI: swagger.default}));
    }).catch((failure) => { if (active) setError(failure); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (!view) return;
    view.SwaggerUI({
      spec: view.schema,
      dom_id: "#api-reference",
      validatorUrl: null,
      requestInterceptor: (details) => {
        const target = new URL(details.url, location.origin);
        if (token() && target.origin === location.origin) details.headers.Authorization = "Bearer " + token();
        return details;
      },
    });
  }, [view]);
  return <>
    <div className="page-heading"><h1>API reference</h1></div>
    <ErrorSummary error={error} />
    {!view && !error && <p role="status">Loading API reference…</p>}
    <div id="api-reference" />
  </>;
}

function Dashboard({user}) {
  const staff = ["Coordinator", "Approver"].includes(user.role);
  const {data, error} = useResource(staff ? "/api/dashboard" : null);
  const counts = data?.counts;
  let next = ["terms", "Set up the active term"];
  if (counts && !counts.slots) next = ["grid", "Set up the weekly grid"];
  else if (counts && !counts.rooms) next = ["rooms", "Add rooms"];
  else if (counts && !counts.offerings) next = ["offerings", "Add offerings"];
  else if (counts) next = ["offerings", "Review offerings"];
  return <>
    <div className="page-heading"><div><h1>Dashboard</h1><p>{roleDescription[user.role]}</p></div></div>
    <ErrorSummary error={error} />
    <section className="panel welcome">
      <div className="welcome-avatar" aria-hidden="true">{user.full_name.slice(0, 1).toUpperCase()}</div>
      <div><h2>Welcome, {user.full_name}</h2><p>{user.role}</p></div>
      {user.role === "Administrator" && <a className="primary" href="#users">Manage accounts</a>}
      {!staff && <div className="form-actions">
        <a className="secondary" href="#published-timetable">Published timetable</a>
        <a className="secondary" href="#published-exams">Published exams</a>
      </div>}
    </section>
    {staff && data && <section className="panel dashboard-term">
      <div className="section-heading"><div>
        <h2>{data.active_term ? data.active_term.name : "No active term"}</h2>
        <p>{data.active_term ? "Active term" : "Create or activate a term to start preparing its timetable."}</p>
      </div>
      <div className="form-actions">
        {user.role === "Coordinator" && data.active_term &&
          <a className="primary" href="#generate">Generate timetable</a>}
        <a className={user.role === "Coordinator" && data.active_term ? "secondary" : "primary"}
          href={"#master/" + next[0]}>{user.role === "Coordinator" ? next[1] : "View master data"}</a>
      </div></div>
      {counts && <dl className="term-counts">
        <div><dt>Open weekly slots</dt><dd>{counts.slots}</dd></div>
        <div><dt>Active rooms</dt><dd>{counts.rooms}</dd></div>
        <div><dt>Offerings</dt><dd>{counts.offerings}</dd></div>
      </dl>}
      {data.schedules && <div className="dashboard-schedules">
        {Object.entries(data.schedules).map(([kind, schedule]) => <div key={kind}>
          <strong>{kind === "Exam" ? "Exam schedule" : "Timetable"}</strong>
          {schedule ? <a href={"#schedules/" + schedule.schedule_id}>Version {schedule.version_no} · {schedule.status}</a>
            : <span>No versions</span>}
        </div>)}
      </div>}
    </section>}
  </>;
}

function Workspace({user, signOut}) {
  const [path, setPath] = useState(location.hash.slice(1) || "dashboard");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState(null);
  const admin = user.role === "Administrator";
  const masterAccess = ["Coordinator", "Approver"].includes(user.role);
  const availabilityAccess = ["Coordinator", "Faculty"].includes(user.role);
  useEffect(() => {
    const nav = () => { setPath(location.hash.slice(1) || "dashboard"); setNotice(""); setError(null); };
    window.addEventListener("hashchange", nav);
    return () => window.removeEventListener("hashchange", nav);
  }, []);

  async function logout() {
    try {
      await request("/auth/logout", {method: "POST"});
      signOut("You signed out.");
    } catch (failure) {
      setError(failure);
    }
  }

  const links = [
    ["dashboard", "Dashboard"],
    ...(masterAccess ? [["master/terms", "Master data"]] : []),
    ...(availabilityAccess ? [["availability", "Availability"]] : []),
    ...(user.role === "Coordinator" ? [["import", "Import CSV"], ["settings", "Settings"]] : []),
    ...(masterAccess ? [["versions", "Timetables"], ["exam-versions", "Exams"]] : []),
    ...(!masterAccess ? [["published-timetable", "Timetable"], ["published-exams", "Exams"]] : []),
    ...(admin ? [["users", "User accounts"], ["audit", "Audit log"], ["api-reference", "API reference"]] : []),
    ["password", "Change password"],
  ];

  let content;
  if (path === "dashboard") content = <Dashboard user={user} />;
  else if (path.startsWith("master/") && masterAccess) {
    content = <MasterData key={path} section={path.slice(7)} user={user} notify={setNotice} />;
  }
  else if (path === "availability" && availabilityAccess) content = <Availability user={user} notify={setNotice} />;
  else if (path === "generate" && user.role === "Coordinator") content = <Generate />;
  else if (path === "generate-exams" && user.role === "Coordinator") content = <Generate key="generate-exams" exam />;
  else if (path === "import" && user.role === "Coordinator") content = <ImportWizard />;
  else if (path === "settings" && user.role === "Coordinator") content = <Settings />;
  else if (path === "versions" && masterAccess) content = <Versions user={user} />;
  else if (path === "exam-versions" && masterAccess) content = <Versions key="exam-versions" user={user} exam />;
  else if (masterAccess && /^schedules\/\d+$/.test(path)) content = <RunView key={path} id={path.split("/")[1]} user={user} />;
  else if (masterAccess && /^timetable\/\d+$/.test(path)) content = <TimetableView key={path} id={path.split("/")[1]} user={user} />;
  else if (masterAccess && /^exams\/\d+$/.test(path)) content = <ExamView key={path} id={path.split("/")[1]} user={user} />;
  else if (path === "published-timetable") content = <Published key={path} View={TimetableView} user={user} />;
  else if (path === "published-exams") content = <Published key={path} View={ExamView} user={user} exam />;
  else if (path === "users" && admin) content = <Users current={user} notify={setNotice} />;
  else if (path === "audit" && admin) content = <Audit />;
  else if (path.startsWith("help/")) content = <Help previous={path.slice(5)} />;
  else if (path === "password") content = <ChangePassword done={signOut} cancel={() => { location.hash = "dashboard"; }} />;
  else if (path === "api-reference" && admin) content = <ApiReference />;
  else content = <><div className="page-heading"><h1>Page unavailable</h1></div>
    <p>Your role does not have access to this page.</p><a href="#dashboard">Return to dashboard</a></>;

  return <div className="workspace">
    <a className="skip" href="#page-content" onClick={(event) => {
      event.preventDefault(); document.getElementById("page-content").focus();
    }}>Skip to content</a>
    <header className="topbar"><Brand /><div className="identity">
      <div><strong>{user.full_name}</strong><span>{user.role}</span></div>
      <button className="secondary" onClick={logout}>Sign out</button>
    </div></header>
    <nav className="nav" aria-label="Workspace">
      {links.map(([id, label]) => <a key={id} aria-current={id === path ||
        (id === "master/terms" && path.startsWith("master/")) ? "page" : undefined} href={"#" + id}>{label}</a>)}
      {!path.startsWith("help/") && <a className="help-link" href={"#help/" + path}>Help</a>}
    </nav>
    <main className="content" id="page-content" tabIndex={-1}>
      <ErrorSummary error={error} />
      {notice && <p className="notice" role="status">{notice}</p>}
      {content}
    </main>
  </div>;
}

function App() {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(!!token());
  const [message, setMessage] = useState("");
  function signOut(reason) {
    setToken(null);
    setUser(null);
    setMessage(reason);
    history.replaceState(null, "", "/");
  }

  useEffect(() => {
    const expired = () => signOut("Your session has ended. Sign in again.");
    window.addEventListener("ates-expired", expired);
    if (token()) request("/auth/session").then(setUser).catch((error) => setMessage(error.message))
      .finally(() => setChecking(false));
    return () => window.removeEventListener("ates-expired", expired);
  }, []);

  if (checking) return <main className="content"><p role="status">Checking your session…</p></main>;
  if (!user) return <Login message={message} onLogin={(account) => {
    history.replaceState(null, "", "/#dashboard");
    setUser(account);
    setMessage("");
  }} />;
  return <Workspace user={user} signOut={signOut} />;
}

createRoot(document.getElementById("root")).render(<App />);

