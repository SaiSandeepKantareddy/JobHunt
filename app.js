const stateKey = "personal-job-radar-v1";
let jobs = [];
let tracker = JSON.parse(localStorage.getItem(stateKey) || "{}");
let supabaseClient = null;
let syncUser = null;
let syncChannel = null;

const $ = (id) => document.getElementById(id);
const controls = ["search", "family", "mode", "status"].map($);
const supabaseSettings = window.JOB_RADAR_SUPABASE || {};

const prettyDate = value => value ? new Intl.DateTimeFormat(undefined, {month:"short", day:"numeric", year:"numeric"}).format(new Date(value)) : "Date unavailable";
const statusFor = id => tracker[id] || {};
const hasSyncConfig = () => Boolean(supabaseSettings.url && supabaseSettings.publishableKey && window.supabase);
const isEmptyStatus = status => !status.saved && !status.applied && !status.hidden && !String(status.notes || "").trim();
const stageFor = status => status.hidden ? "hidden" : status.applied ? "applied" : status.saved ? "saved" : "open";

function cleanStatus(status) {
  return {
    saved: Boolean(status.saved),
    applied: Boolean(status.applied),
    hidden: Boolean(status.hidden),
    notes: String(status.notes || ""),
    stage: status.stage || stageFor(status)
  };
}

function saveTracker() {
  localStorage.setItem(stateKey, JSON.stringify(tracker));
}

function setSyncStatus(text) {
  $("sync-status").textContent = text;
}

function rowToStatus(row) {
  return cleanStatus({
    saved: row.saved,
    applied: row.applied,
    hidden: row.hidden,
    notes: row.notes,
    stage: row.stage
  });
}

async function writeRemoteStatus(jobId, status) {
  if (!supabaseClient || !syncUser) return;
  if (isEmptyStatus(status)) {
    const { error } = await supabaseClient.from("job_tracker").delete().eq("user_id", syncUser.id).eq("job_id", jobId);
    if (error) throw error;
    return;
  }
  const { error } = await supabaseClient.from("job_tracker").upsert({
    user_id: syncUser.id,
    job_id: jobId,
    saved: status.saved,
    applied: status.applied,
    hidden: status.hidden,
    notes: status.notes,
    stage: stageFor(status)
  });
  if (error) throw error;
}

async function toggle(id, field) {
  const current = cleanStatus(statusFor(id));
  current[field] = !current[field];
  current.stage = stageFor(current);
  if (isEmptyStatus(current)) {
    delete tracker[id];
  } else {
    tracker[id] = current;
  }
  saveTracker();
  render();
  try {
    await writeRemoteStatus(id, current);
  } catch (error) {
    setSyncStatus("Sync issue - saved locally");
  }
}

async function loadRemoteTracker() {
  const { data, error } = await supabaseClient
    .from("job_tracker")
    .select("job_id,saved,applied,hidden,notes,stage,updated_at")
    .eq("user_id", syncUser.id);
  if (error) throw error;
  for (const row of data || []) tracker[row.job_id] = rowToStatus(row);
  saveTracker();
}

async function pushLocalTracker() {
  const entries = Object.entries(tracker).map(([jobId, status]) => [jobId, cleanStatus(status)]);
  for (const [jobId, status] of entries) await writeRemoteStatus(jobId, status);
}

function subscribeToRemoteTracker() {
  if (syncChannel) supabaseClient.removeChannel(syncChannel);
  syncChannel = supabaseClient
    .channel(`job-tracker-${syncUser.id}`)
    .on("postgres_changes", {
      event: "*",
      schema: "public",
      table: "job_tracker",
      filter: `user_id=eq.${syncUser.id}`
    }, payload => {
      const row = payload.new || payload.old;
      if (!row || !row.job_id) return;
      if (payload.eventType === "DELETE") delete tracker[row.job_id];
      else tracker[row.job_id] = rowToStatus(row);
      saveTracker();
      render();
    })
    .subscribe();
}

async function activateSync(session) {
  syncUser = session.user;
  $("sync-email").hidden = true;
  $("sync-submit").hidden = true;
  $("sync-signout").hidden = false;
  setSyncStatus(`Synced as ${syncUser.email || "signed-in user"}`);
  await loadRemoteTracker();
  await pushLocalTracker();
  subscribeToRemoteTracker();
  render();
}

async function initSync() {
  if (!hasSyncConfig()) {
    setSyncStatus("Local-only tracking");
    return;
  }
  try {
    supabaseClient = window.supabase.createClient(supabaseSettings.url, supabaseSettings.publishableKey);
    const { data } = await supabaseClient.auth.getSession();
    if (data.session) await activateSync(data.session);
    else setSyncStatus("Local now - enter email to sync");
  } catch (error) {
    setSyncStatus("Sync unavailable - local tracking");
  }
}

function populateFamilies() {
  [...new Set(jobs.map(j => j.family))].sort().forEach(family => {
    const option = document.createElement("option"); option.value = family; option.textContent = family; $("family").append(option);
  });
}

function filteredJobs() {
  const query = $("search").value.trim().toLowerCase();
  const selectedStatus = $("status").value;
  return jobs.filter(job => {
    const personal = statusFor(job.id);
    const haystack = `${job.title} ${job.company} ${job.description} ${(job.skills || []).join(" ")}`.toLowerCase();
    const processed = personal.hidden || personal.applied;
    return (!query || haystack.includes(query)) && (!$("family").value || job.family === $("family").value)
      && (!$("mode").value || job.work_mode.toLowerCase().includes($("mode").value))
      && (!selectedStatus || personal[selectedStatus])
      && (selectedStatus || !processed);
  });
}

function render() {
  const visible = filteredJobs(); const container = $("jobs"); container.textContent = "";
  $("result-count").textContent = `${visible.length} role${visible.length === 1 ? "" : "s"}`;
  $("empty").hidden = visible.length !== 0;
  visible.forEach(job => {
    const card = $("job-template").content.cloneNode(true); const article = card.querySelector("article");
    card.querySelector(".score strong").textContent = job.score;
    card.querySelector(".company").textContent = job.company;
    card.querySelector("h2").textContent = job.title;
    card.querySelector(".new-badge").hidden = !job.is_new;
    card.querySelector(".meta").textContent = `${job.location} · ${job.work_mode} · ${prettyDate(job.posted_at)} · ${job.family}`;
    card.querySelector(".description").textContent = job.description;
    job.why.forEach(reason => { const el=document.createElement("span"); el.className="reason"; el.textContent=reason; card.querySelector(".reasons").append(el); });
    (job.skills || []).slice(0,8).forEach(skill => { const el=document.createElement("span"); el.className="skill"; el.textContent=skill; card.querySelector(".skills").append(el); });
    const apply = card.querySelector(".apply"); apply.href = job.url;
    article.querySelectorAll("button[data-action]").forEach(button => {
      const action=button.dataset.action; if (statusFor(job.id)[action]) button.classList.add("active");
      button.addEventListener("click", () => toggle(job.id, action));
    });
    container.append(card);
  });
}

function exportCsv() {
  const rows = [["score","title","company","location","posted","family","url"], ...filteredJobs().map(j => [j.score,j.title,j.company,j.location,j.posted_at,j.family,j.url])];
  const csv = rows.map(row => row.map(value => `"${String(value ?? "").replaceAll('"','""')}"`).join(",")).join("\n");
  const link=document.createElement("a"); link.href=URL.createObjectURL(new Blob([csv],{type:"text/csv"})); link.download="job-shortlist.csv"; link.click(); URL.revokeObjectURL(link.href);
}

async function boot() {
  try {
    const response=await fetch("data/jobs.json", {cache:"no-store"}); if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload=await response.json(); jobs=payload.jobs || []; populateFamilies();
    $("stats").innerHTML=`<span class="stat"><strong>${jobs.length}</strong> matches</span><span class="stat"><strong>${payload.new_count || 0}</strong> new</span><span class="stat"><strong>$0</strong> API cost</span>`;
    $("updated").textContent=payload.generated_at ? `Updated ${prettyDate(payload.generated_at)}` : "Run the fetcher to begin";
    render();
    await initSync();
  } catch (error) { $("result-count").textContent="Could not load jobs. Start a local web server; see README."; }
}

controls.forEach(control => control.addEventListener("input", render));
$("export").addEventListener("click", exportCsv);
$("sync-panel").addEventListener("submit", async event => {
  event.preventDefault();
  if (!supabaseClient) return setSyncStatus("Add Supabase config first");
  const email = $("sync-email").value.trim();
  if (!email) return;
  const { error } = await supabaseClient.auth.signInWithOtp({
    email,
    options: { emailRedirectTo: window.location.href.split("#")[0] }
  });
  setSyncStatus(error ? "Could not send sign-in link" : "Check email for sync link");
});
$("sync-signout").addEventListener("click", async () => {
  if (syncChannel) supabaseClient.removeChannel(syncChannel);
  await supabaseClient.auth.signOut();
  syncUser = null;
  syncChannel = null;
  $("sync-email").hidden = false;
  $("sync-submit").hidden = false;
  $("sync-signout").hidden = true;
  setSyncStatus("Signed out - local tracking");
});
boot();
