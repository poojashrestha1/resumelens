import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BriefcaseBusiness,
  ArrowRight,
  ShieldCheck,
  Users,
  UserCircle,
  FileText,
  LogOut,
  RefreshCw,
  Upload,
  Search,
  CheckCircle2,
  Plus,
  LockKeyhole,
  Mail,
  ChevronLeft,
} from "lucide-react";
import "./style.css";
const API = import.meta.env.VITE_API_URL || "";
const statusLabels = {
  applied: "Applied",
  in_review: "In review",
  interview: "Interview",
  rejected: "Not selected",
  offer: "Offer",
};
async function fetchJSON(path, options = {}) {
  const response = await fetch(API + path, options);
  let value;
  try {
    value = await response.json();
  } catch {
    value = { detail: "Unexpected server response" };
  }
  if (!response.ok)
    throw Error(
      typeof value.detail === "string" ? value.detail : "Request failed",
    );
  return value;
}
function ApplicantForm({ job, token, onClose, onSubmitted, onError }) {
  const empty = {
    name: "",
    email: "",
    phone: "",
    address: "",
    skills: "",
    education: "",
    experience: "",
    volunteer_experience: "",
    projects: "",
    leadership: "",
    cover_letter: "",
  };
  const [fields, setFields] = useState(empty);
  const [resume, setResume] = useState(null);
  const [coverPDF, setCoverPDF] = useState(null);
  const [busy, setBusy] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [message, setMessage] = useState("");
  const [dirty, setDirty] = useState({});
  const dirtyRef = React.useRef({});
  const [processingSeconds, setProcessingSeconds] = useState(null);
  function change(key, value) {
    dirtyRef.current[key] = true;
    setDirty({ ...dirtyRef.current });
    setFields((old) => ({ ...old, [key]: value }));
  }
  async function uploadForPrefill(file) {
    setResume(file);
    setMessage("");
    if (!file) return;
    setExtracting(true);
    setProcessingSeconds(null);
    const fd = new FormData();
    fd.append("resume", file);
    const start = performance.now();
    try {
      const response = await fetch(`${API}/api/applications/prefill`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      const body = await response.json();
      if (!response.ok) throw Error(body.detail || "Could not extract résumé");
      const conversion = {
        detected_name: "name",
        skills: "skills",
        education: "education",
        experience: "experience",
        volunteer_experience: "volunteer_experience",
        projects: "projects",
        leadership: "leadership",
      };
      setFields((old) => {
        const next = { ...old };
        for (const [from, to] of Object.entries(conversion)) {
          if (!dirtyRef.current[to] && body[from])
            next[to] = Array.isArray(body[from])
              ? body[from].join(", ")
              : body[from];
        }
        return next;
      });
      setProcessingSeconds(((performance.now() - start) / 1000).toFixed(1));
      setMessage(
        (body.extraction_method === "manual_required"
          ? "This PDF needs manual entry. "
          : "Résumé prefilled. ") +
          (body.processing_warning ||
            "Review and correct every field before submitting."),
      );
    } catch (e) {
      setMessage(
        "Auto-fill unavailable: " +
          e.message +
          ". You can still complete the form manually.",
      );
    } finally {
      setExtracting(false);
    }
  }
  async function submitApplication(event) {
    event.preventDefault();
    if (extracting) {
      setMessage("Finish reviewing extracted fields before submitting.");
      return;
    }
    setBusy(true);
    onError("");
    try {
      const details = {
        ...fields,
        skills: fields.skills
          .split(/[,;\n]/)
          .map((x) => x.trim())
          .filter(Boolean),
      };
      const data = new FormData();
      data.append("job_id", job.id);
      data.append("details", JSON.stringify(details));
      if (resume) data.append("resume", resume);
      if (coverPDF) data.append("cover_file", coverPDF);
      const r = await fetch(`${API}/api/applications`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: data,
      });
      const body = await r.json();
      if (!r.ok)
        throw Error(
          typeof body.detail === "string" ? body.detail : "Application failed",
        );
      onSubmitted();
    } catch (e) {
      onError(e.message);
    } finally {
      setBusy(false);
    }
  }
  const field = (key, title, required = false, multiline = false) => (
    <label key={key}>
      {title}
      {multiline ? (
        <textarea
          value={fields[key]}
          onChange={(e) => change(key, e.target.value)}
          rows={3}
          required={required}
        />
      ) : (
        <input
          value={fields[key]}
          onChange={(e) => change(key, e.target.value)}
          required={required}
          type={key === "email" ? "email" : key === "phone" ? "tel" : "text"}
        />
      )}
      {dirty[key] && <small className="verified-note">Manually edited</small>}
    </label>
  );
  return (
    <div
      className="overlay"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="modal application-modal">
        <button
          className="close"
          onClick={onClose}
          aria-label="Close application"
        >
          ×
        </button>
        <div className="eyebrow">APPLICATION FORM</div>
        <h2>Apply for {job.title}</h2>
        <p className="muted">
          Upload your résumé to autofill, or enter everything manually. You
          control the final information.
        </p>
        <div className="autofill-box">
          <label>
            Auto-fill from résumé (PDF, max 5 MB; optional)
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => uploadForPrefill(e.target.files[0])}
            />
          </label>
          {extracting ? (
            <p role="status">Extracting… You can begin typing while we work.</p>
          ) : message ? (
            <p role="status">{message}</p>
          ) : (
            <p className="muted">
              For scanned PDFs, extraction may take longer. All fields remain
              editable.
            </p>
          )}
          {processingSeconds && (
            <small>
              Preview time: {processingSeconds} seconds (including upload)
            </small>
          )}
        </div>
        <form className="application-form" onSubmit={submitApplication}>
          <h3>Personal information</h3>
          <div className="form-grid">
            {field("name", "Full name", true)}
            {field("email", "Email", true)}
            {field("phone", "Contact number", true)}
            {field("address", "Address", true)}
          </div>
          <h3>Qualifications</h3>
          {field("skills", "Skills (separate with commas)", false, true)}
          {field("education", "Education", false, true)}
          {field("experience", "Work experience", false, true)}
          {field("projects", "Projects", false, true)}
          {field("volunteer_experience", "Volunteer experience", false, true)}
          {field("leadership", "Leadership", false, true)}
          <h3>Cover letter</h3>
          {field("cover_letter", "Cover letter text (optional)", false, true)}
          <label>
            Or attach a cover letter (PDF, optional)
            <input
              type="file"
              accept="application/pdf,.pdf"
              onChange={(e) => setCoverPDF(e.target.files[0])}
            />
          </label>
          <p className="muted">
            Review the details above carefully. Submitted values take priority
            over automatic résumé extraction.
          </p>
          <button className="primary wide" disabled={busy || extracting}>
            {busy ? "Submitting…" : "Submit application"}{" "}
            <ArrowRight size={16} />
          </button>
        </form>
      </div>
    </div>
  );
}
function App() {
  const [token, setToken] = useState(sessionStorage.getItem("token") || "");
  const [role, setRole] = useState(sessionStorage.getItem("role") || "");
  const [route, setRoute] = useState(location.pathname);
  const [authMode, setAuthMode] = useState("login");
  const [email, setEmail] = useState("");
  const [session, setSession] = useState("");
  const [jobs, setJobs] = useState([]);
  const [staffJobs, setStaffJobs] = useState([]);
  const [editingJob, setEditingJob] = useState(null);
  const [applications, setApplications] = useState([]);
  const [recruiters, setRecruiters] = useState([]);
  const [awsInfo, setAwsInfo] = useState(null);
  const [chosen, setChosen] = useState(null);
  const [tab, setTab] = useState("applications");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [active, setActive] = useState(null);
  const auth = { Authorization: `Bearer ${token}` };
  const call = (path, method = "GET", body = null) =>
    fetchJSON(path, {
      method,
      headers: {
        ...auth,
        ...(body ? { "Content-Type": "application/json" } : {}),
      },
      ...(body ? { body: JSON.stringify(body) } : {}),
    });
  function go(path) {
    history.pushState({}, "", path);
    setRoute(path);
    setNotice("");
    setError("");
    window.scrollTo(0, 0);
  }
  useEffect(() => {
    const cb = () => setRoute(location.pathname);
    addEventListener("popstate", cb);
    return () => removeEventListener("popstate", cb);
  }, []);
  useEffect(() => {
    fetchJSON("/api/jobs")
      .then(setJobs)
      .catch((e) => setError(e.message));
  }, []);
  async function load() {
    try {
      if (!token) return;
      const user = await call("/api/me");
      setRole(user.role);
      sessionStorage.setItem("role", user.role);
      const data = await call(
        user.role === "applicant"
          ? "/api/me/applications"
          : "/api/staff/applications",
      );
      setApplications(data);
      if (user.role !== "applicant") {
        setStaffJobs(await call("/api/staff/jobs"));
        setAwsInfo(await call("/api/staff/aws-resources"));
      }
      if (user.role === "admin")
        setRecruiters(await call("/api/admin/recruiters"));
    } catch (e) {
      if (e.message.includes("Invalid") || e.message.includes("session"))
        logout();
      else setError(e.message);
    }
  }
  useEffect(() => {
    if (token) {
      load();
      const timer = setInterval(load, 20000);
      return () => clearInterval(timer);
    }
  }, [token]);
  function logout() {
    sessionStorage.removeItem("token");
    sessionStorage.removeItem("role");
    setToken("");
    setRole("");
    go("/");
  }
  async function handleAuth(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    const f = Object.fromEntries(new FormData(e.currentTarget));
    setEmail(f.email || email);
    try {
      if (authMode === "signup") {
        const r = await fetchJSON("/api/auth/signup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: f.email, password: f.password }),
        });
        setNotice(r.message);
        setAuthMode("confirm");
      } else if (authMode === "confirm") {
        const r = await fetchJSON("/api/auth/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: f.email, code: f.code }),
        });
        setNotice(r.message);
        setAuthMode("login");
      } else {
        const endpoint =
          authMode === "challenge" ? "/api/auth/challenge" : "/api/auth/login";
        const body =
          authMode === "challenge"
            ? { email: f.email, password: f.password, session }
            : { email: f.email, password: f.password };
        const r = await fetchJSON(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (r.challenge) {
          setSession(r.session);
          setAuthMode("challenge");
          setNotice(
            "Set a new permanent password to complete the recruiter invitation.",
          );
        } else {
          sessionStorage.setItem("token", r.access_token);
          setToken(r.access_token);
          if (r.role) {
            setRole(r.role);
            sessionStorage.setItem("role", r.role);
          }
          go("/dashboard");
        }
      }
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  }
  async function openPDF(a) {
    try {
      const r = await fetch(`${API}/api/applications/${a.id}/resume`, {
        headers: auth,
      });
      if (!r.ok) throw Error("Unable to retrieve PDF");
      const url = URL.createObjectURL(await r.blob());
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (ex) {
      setError(ex.message);
    }
  }
  async function openDocument(a, kind) {
    try {
      const r = await fetch(`${API}/api/applications/${a.id}/${kind}`, {
        headers: auth,
      });
      if (!r.ok) throw Error("Unable to retrieve PDF");
      const url = URL.createObjectURL(await r.blob());
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (ex) {
      setError(ex.message);
    }
  }
  async function setReview(a, s) {
    try {
      await call(`/api/staff/applications/${a.id}/status`, "PATCH", {
        status: s,
      });
      setNotice("Application status updated");
      await load();
    } catch (ex) {
      setError(ex.message);
    }
  }
  async function invite(e) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const f = new FormData(e.currentTarget);
      const r = await call("/api/admin/recruiters", "POST", {
        email: f.get("email"),
      });
      setNotice(r.message);
      e.currentTarget.reset();
      await load();
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  }
  async function toggleRecruiter(r) {
    try {
      await call(
        `/api/admin/recruiters/${encodeURIComponent(r.username)}/${r.enabled ? "disable" : "enable"}`,
        "POST",
      );
      setNotice("Recruiter updated");
      await load();
    } catch (ex) {
      setError(ex.message);
    }
  }
  async function createJob(e) {
    e.preventDefault();
    const form = e.currentTarget; // Save form reference here
    setBusy(true);

    try {
      const f = Object.fromEntries(new FormData(form));

      const body = {
        ...f,
        active: editingJob ? editingJob.active : true,
      };

      const job = await call(
        editingJob ? `/api/staff/jobs/${editingJob.id}` : "/api/staff/jobs",
        editingJob ? "PATCH" : "POST",
        body,
      );

      setJobs(await fetchJSON("/api/jobs"));
      setStaffJobs(await call("/api/staff/jobs"));

      setNotice(`${editingJob ? "Updated" : "Created"} ${job.title}`);
      setEditingJob(null);

      form.reset(); // Fixed!
    } catch (ex) {
      setError(ex.message);
    } finally {
      setBusy(false);
    }
  }
  async function archiveJob(j) {
    if (!confirm(`Archive ${j.title}? Existing applications will be retained.`))
      return;
    try {
      await call(`/api/staff/jobs/${j.id}`, "DELETE");
      setStaffJobs(await call("/api/staff/jobs"));
      setJobs(await fetchJSON("/api/jobs"));
      setNotice("Position archived");
    } catch (ex) {
      setError(ex.message);
    }
  }
  async function searchCandidates(value) {
    setSearch(value);
    if (!isStaff) return;
    try {
      setApplications(
        await call(`/api/staff/applications?q=${encodeURIComponent(value)}`),
      );
    } catch (ex) {
      setError(ex.message);
    }
  }
  const visible = useMemo(
    () =>
      applications.filter(
        (a) =>
          !search ||
          [
            a.name,
            a.position,
            a.education,
            a.skills,
            a.experience,
            a.volunteer_experience,
            a.projects,
            a.leadership,
            a.address,
            a.cover_letter,
            a.resume_text,
          ]
            .join(" ")
            .toLowerCase()
            .includes(search.toLowerCase()),
      ),
    [applications, search],
  );
  const isStaff = role === "admin" || role === "hr";
  return (
    <>
      <header className="topbar">
        <button className="logo" onClick={() => go("/")}>
          <span className="mark">
            <BriefcaseBusiness size={21} />
          </span>
          resumelens<span className="blue">.</span>
        </button>
        <nav>
          <button onClick={() => go("/")}>Open roles</button>
          {token ? (
            <>
              <button onClick={() => go("/dashboard")}>My workspace</button>
              <button onClick={logout}>
                <LogOut size={16} /> Sign out
              </button>
            </>
          ) : (
            <button
              className="pillbtn"
              onClick={() => {
                setAuthMode("login");
                go("/login");
              }}
            >
              Sign in <ArrowRight size={16} />
            </button>
          )}
        </nav>
      </header>
      {notice && (
        <div className="flash good" role="status">
          <CheckCircle2 size={18} />
          {notice}
          <button onClick={() => setNotice("")}>×</button>
        </div>
      )}
      {error && (
        <div className="flash bad" role="alert">
          {error}
          <button onClick={() => setError("")}>×</button>
        </div>
      )}
      {route === "/login" || (!token && route === "/dashboard") ? (
        <main className="authwrap">
          <div className="authcard">
            <div className="cardicon">
              <LockKeyhole />
            </div>
            <h1>
              {authMode === "signup"
                ? "Create applicant account"
                : authMode === "confirm"
                  ? "Verify your email"
                  : authMode === "challenge"
                    ? "Set new password"
                    : "Welcome back"}
            </h1>
            <p>
              {authMode === "signup"
                ? "Sign up to apply and track your applications."
                : authMode === "confirm"
                  ? "Enter the code Cognito sent to your email."
                  : authMode === "challenge"
                    ? "Your recruiter invitation requires a permanent password."
                    : "Sign in as an applicant, HR recruiter, or administrator."}
            </p>
            <form onSubmit={handleAuth}>
              <label>
                Email
                <input
                  type="email"
                  name="email"
                  required
                  defaultValue={email}
                  autoComplete="username"
                />
              </label>
              {authMode === "confirm" ? (
                <label>
                  Verification code
                  <input name="code" required />
                </label>
              ) : (
                <label>
                  {authMode === "challenge"
                    ? "New permanent password"
                    : "Password"}
                  <input
                    type="password"
                    name="password"
                    minLength={8}
                    required
                    autoComplete={
                      authMode === "login" ? "current-password" : "new-password"
                    }
                  />
                </label>
              )}
              <button disabled={busy} className="primary wide">
                {busy
                  ? "Working…"
                  : authMode === "signup"
                    ? "Create account"
                    : authMode === "confirm"
                      ? "Confirm email"
                      : authMode === "challenge"
                        ? "Set password"
                        : "Sign in"}{" "}
                <ArrowRight size={17} />
              </button>
            </form>
            <div className="authswitch">
              {authMode === "login" ? (
                <button
                  onClick={() => {
                    setAuthMode("signup");
                    setError("");
                  }}
                >
                  New applicant? Create account
                </button>
              ) : (
                <button
                  onClick={() => {
                    setAuthMode("login");
                    setError("");
                  }}
                >
                  Back to sign in
                </button>
              )}
            </div>
          </div>
        </main>
      ) : route === "/dashboard" && token ? (
        <main className="dashboard">
          <aside>
            <div className="eyebrow">{role.toUpperCase()} WORKSPACE</div>
            <button
              className={tab === "applications" ? "selected" : ""}
              onClick={() => setTab("applications")}
            >
              <FileText size={18} />
              {isStaff ? "Applications" : "My Applications"}
            </button>
            {role === "admin" && (
              <>
                <button
                  className={tab === "recruiters" ? "selected" : ""}
                  onClick={() => setTab("recruiters")}
                >
                  <Users size={18} />
                  Manage recruiters
                </button>
              </>
            )}
            {isStaff && (
              <button
                className={tab === "jobs" ? "selected" : ""}
                onClick={() => setTab("jobs")}
              >
                <BriefcaseBusiness size={18} />
                Manage positions
              </button>
            )}
            {isStaff && (
              <button
                className={tab === "aws" ? "selected" : ""}
                onClick={() => setTab("aws")}
              >
                <ShieldCheck size={18} />
                AWS Processing
              </button>
            )}
            <button onClick={() => go("/")}>
              <ChevronLeft size={18} />
              Back to careers
            </button>
          </aside>
          <section className="workspace">
            <div className="eyebrow">RESUMELENS PORTAL</div>
            <h1>
              {tab === "applications"
                ? isStaff
                  ? "Candidate applications"
                  : "My applications"
                : tab === "recruiters"
                  ? "Recruiter accounts"
                  : tab === "aws"
                    ? "AWS processing resources"
                    : "Job management"}
            </h1>
            <p className="muted">
              {tab === "applications"
                ? "Review submitted applications and their progress."
                : tab === "recruiters"
                  ? "Invite and manage your HR team."
                  : tab === "aws"
                    ? "Service roles and observed résumé processing results."
                    : "Manage open and archived positions."}
            </p>
            {tab === "applications" ? (
              <>
                <div className="stats">
                  <div>
                    <small>Total applications</small>
                    <strong>{applications.length}</strong>
                  </div>
                  <div>
                    <small>In review</small>
                    <strong>
                      {
                        applications.filter(
                          (a) => a.review_status === "in_review",
                        ).length
                      }
                    </strong>
                  </div>
                  <div>
                    <small>Interviews</small>
                    <strong>
                      {
                        applications.filter(
                          (a) => a.review_status === "interview",
                        ).length
                      }
                    </strong>
                  </div>
                </div>
                <div className="panel">
                  <div className="paneltop">
                    <h2>Applications</h2>
                    <button onClick={load} className="secondary">
                      <RefreshCw size={16} /> Refresh
                    </button>
                  </div>
                  <div className="search">
                    <Search size={18} />
                    <input
                      placeholder="Search all résumé keywords, skills, education, experience"
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                    />
                  </div>
                  <div className="scroll">
                    <table>
                      <thead>
                        <tr>
                          {isStaff ? (
                            <>
                              <th>Name</th>
                              <th>Contact</th>
                              <th>Skills</th>
                              <th>Education</th>
                              <th>Experience</th>
                              <th>Volunteer experience</th>
                              <th>Projects</th>
                              <th>Leadership</th>
                              <th>Cover letter</th>
                              <th>Position</th>
                              <th>Review</th>
                              <th>Processing</th>
                              <th>CV</th>
                            </>
                          ) : (
                            <>
                              <th>Position</th>
                              <th>Review status</th>
                              <th>Processing</th>
                              <th>CV</th>
                            </>
                          )}
                        </tr>
                      </thead>
                      <tbody>
                        {visible.map((a) => (
                          <tr key={a.id}>
                            {isStaff ? (
                              <>
                                <td>
                                  <strong>{a.name}</strong>
                                  <small>
                                    {new Date(
                                      a.created_at,
                                    ).toLocaleDateString()}
                                  </small>
                                </td>
                                <td className="education">
                                  {a.email || ""}
                                  <small>{a.phone || ""}</small>
                                  <small>{a.address || ""}</small>
                                </td>
                                <td className="education">
                                  {Array.isArray(a.skills)
                                    ? a.skills.join(", ")
                                    : a.skills}
                                </td>
                                <td className="education">
                                  {a.education || "Not detected"}
                                </td>
                                <td className="education">
                                  {a.experience || "Not listed"}
                                </td>
                                <td className="education">
                                  {a.volunteer_experience || "Not listed"}
                                </td>
                                <td className="education">
                                  {a.projects || "Not listed"}
                                </td>
                                <td className="education">
                                  {a.leadership || "Not listed"}
                                </td>
                                <td className="education">
                                  {a.cover_letter || "Not provided"}
                                  {a.cover_letter_key && (
                                    <button
                                      className="link"
                                      onClick={() =>
                                        openDocument(a, "cover-letter")
                                      }
                                    >
                                      PDF
                                    </button>
                                  )}
                                </td>
                                <td>{a.position}</td>
                                <td>
                                  <select
                                    value={a.review_status}
                                    onChange={(e) =>
                                      setReview(a, e.target.value)
                                    }
                                  >
                                    {Object.keys(statusLabels).map((k) => (
                                      <option key={k} value={k}>
                                        {statusLabels[k]}
                                      </option>
                                    ))}
                                  </select>
                                </td>
                                <td>
                                  <span
                                    className="tag"
                                    title={
                                      a.processing_warning ||
                                      a.processing_error ||
                                      ""
                                    }
                                  >
                                    {a.processing_status?.replaceAll("_", " ")}
                                  </span>
                                  <small>
                                    {a.processing_warning ||
                                      a.processing_error ||
                                      ""}
                                  </small>
                                  <small>
                                    {a.processing_duration_ms
                                      ? `Processed in ${(a.processing_duration_ms / 1000).toFixed(1)} s`
                                      : ""}
                                  </small>
                                  <small>
                                    {Array.isArray(a.section_evidence)
                                      ? `Sections: ${a.section_evidence.join(", ")}`
                                      : ""}
                                  </small>
                                </td>
                              </>
                            ) : (
                              <>
                                <td>{a.position}</td>
                                <td>
                                  <span className="tag">
                                    {statusLabels[a.review_status]}
                                  </span>
                                </td>
                                <td>
                                  <span className="tag">
                                    {a.processing_status?.replaceAll("_", " ")}
                                  </span>
                                </td>
                              </>
                            )}
                            <td>
                              {a.resume_key ? (
                                <button
                                  className="link"
                                  onClick={() => openPDF(a)}
                                >
                                  <FileText size={16} /> PDF
                                </button>
                              ) : (
                                <span className="muted">Manual entry</span>
                              )}
                            </td>
                          </tr>
                        ))}
                        {visible.length === 0 && (
                          <tr>
                            <td colSpan={isStaff ? 13 : 4}>
                              No applications found.
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : tab === "recruiters" && role === "admin" ? (
              <>
                <form className="panel simpleform" onSubmit={invite}>
                  <h2>Invite a recruiter</h2>
                  <p className="muted">
                    Cognito sends a temporary password. The recruiter changes it
                    on first sign-in.
                  </p>
                  <label>
                    Recruiter email
                    <input
                      name="email"
                      type="email"
                      required
                      placeholder="recruiter@company.com"
                    />
                  </label>
                  <button className="primary" disabled={busy}>
                    <Plus size={17} /> Send invitation
                  </button>
                </form>
                <div className="panel">
                  <h2>HR team</h2>
                  <div className="scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Email</th>
                          <th>Account</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recruiters.map((r) => (
                          <tr key={r.username || r.email}>
                            <td>{r.email}</td>
                            <td>{r.enabled ? "Enabled" : "Disabled"}</td>
                            <td>
                              <button
                                className="secondary"
                                onClick={() => toggleRecruiter(r)}
                              >
                                {r.enabled ? "Deactivate" : "Activate"}
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              </>
            ) : tab === "aws" && isStaff ? (
              <div className="panel">
                <h2>AWS integration</h2>
                <p className="muted">
                  Service responsibilities are configuration information, not
                  independent live AWS health checks.
                </p>
                <div className="stats">
                  {Object.entries(awsInfo?.processing_counts || {}).map(
                    ([k, v]) => (
                      <div key={k}>
                        <small>{k.replaceAll("_", " ")}</small>
                        <strong>{v}</strong>
                      </div>
                    ),
                  )}
                </div>
                {(awsInfo?.services || []).map((r) => (
                  <div className="jobrow" key={r.name}>
                    <div>
                      <strong>{r.name}</strong>
                      <small>{r.purpose}</small>
                      {r.resource && <small>Resource: {r.resource}</small>}
                    </div>
                  </div>
                ))}
              </div>
            ) : tab === "jobs" && isStaff ? (
              <>
                <form
                  key={editingJob?.id || "new"}
                  className="panel simpleform"
                  onSubmit={createJob}
                >
                  <h2>{editingJob ? "Edit position" : "Post a position"}</h2>
                  {[
                    "title",
                    "department",
                    "location",
                    "type",
                    "description",
                  ].map((f) => (
                    <label key={f}>
                      {f[0].toUpperCase() + f.slice(1)}
                      <input
                        name={f}
                        required
                        defaultValue={
                          editingJob?.[f] || (f === "type" ? "Full-time" : "")
                        }
                      />
                    </label>
                  ))}
                  <button className="primary" disabled={busy}>
                    <Plus size={17} />
                    {editingJob ? "Save changes" : "Publish job"}
                  </button>
                  {editingJob && (
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setEditingJob(null)}
                    >
                      Cancel editing
                    </button>
                  )}
                </form>
                <div className="panel">
                  <h2>All positions (active and archived)</h2>
                  {staffJobs.map((j) => (
                    <div className="jobrow" key={j.id}>
                      <div>
                        <strong>{j.title}</strong>
                        <span>
                          {j.department} · {j.location} ·{" "}
                          {j.active ? "Active" : "Archived"}
                        </span>
                      </div>
                      <button
                        className="secondary"
                        onClick={() => {
                          setEditingJob(j);
                          window.scrollTo(0, 0);
                        }}
                      >
                        Edit
                      </button>
                      {j.active && (
                        <button
                          className="secondary"
                          onClick={() => archiveJob(j)}
                        >
                          Archive
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </section>
        </main>
      ) : (
        <main>
          <section className="hero">
            <div className="eyebrow">
              <span className="dot" /> NOW HIRING
            </div>
            <h1>
              Build something <em>remarkable.</em>
            </h1>
            <p>
              Join a team that values curiosity, innovation, and meaningful
              work. Your next chapter starts here.
            </p>
            <button
              className="primary"
              onClick={() =>
                document
                  .getElementById("jobs")
                  .scrollIntoView({ behavior: "smooth" })
              }
            >
              Explore opportunities <ArrowRight size={18} />
            </button>
            <div className="herofig">
              <div>
                <strong>{jobs.length}</strong>
                <span>Open roles</span>
              </div>
              <div>
                <strong>3</strong>
                <span>Teams hiring</span>
              </div>
              <div>
                <strong>∞</strong>
                <span>Possibilities</span>
              </div>
            </div>
          </section>
          <section className="jobs" id="jobs">
            <div className="eyebrow">EXPLORE THE POSSIBILITIES</div>
            <h2>Open positions</h2>
            <p className="muted">Find the opportunity that's right for you.</p>
            <div className="joblist">
              {jobs.map((j) => (
                <div className="jobrow" key={j.id}>
                  <span className="jobicon">
                    <BriefcaseBusiness size={21} />
                  </span>
                  <div>
                    <strong>{j.title}</strong>
                    <small>{j.description}</small>
                    <span className="jobmeta">
                      {j.department} · {j.location} · {j.type}
                    </span>
                  </div>
                  {(!token || role === "applicant") && (
                    <button
                      className="secondary"
                      onClick={() => {
                        if (!token) {
                          setNotice(
                            "Sign in or create an applicant account before applying.",
                          );
                          setAuthMode("login");
                          go("/login");
                        } else if (role !== "applicant") {
                          setError("Only applicant accounts can apply.");
                        } else {
                          setChosen(j);
                          setError("");
                          window.scrollTo(0, 0);
                        }
                      }}
                    >
                      Apply <ArrowRight size={15} />
                    </button>
                  )}
                </div>
              ))}
            </div>
          </section>
          {chosen && role === "applicant" && (
            <ApplicantForm
              job={chosen}
              token={token}
              onClose={() => setChosen(null)}
              onError={setError}
              onSubmitted={async () => {
                setChosen(null);
                await load();
                go("/dashboard");
                setNotice(
                  "Application submitted. Your reviewed fields have been saved.",
                );
              }}
            />
          )}
        </main>
      )}
      <footer>
        <strong>
          resumelens<span className="blue">.</span>
        </strong>
        <span>Built with React, FastAPI, and AWS</span>
      </footer>
    </>
  );
}
createRoot(document.getElementById("root")).render(<App />);
