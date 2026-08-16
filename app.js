const stateKey = "personal-job-radar-v1";
let jobs = [];
let tracker = JSON.parse(localStorage.getItem(stateKey) || "{}");
const $ = (id) => document.getElementById(id);
const controls = ["search", "family", "mode", "status"].map($);

const prettyDate = value => value ? new Intl.DateTimeFormat(undefined, {month:"short", day:"numeric", year:"numeric"}).format(new Date(value)) : "Date unavailable";
const statusFor = id => tracker[id] || {};
function saveTracker() { localStorage.setItem(stateKey, JSON.stringify(tracker)); }
function toggle(id, status) {
  const current = statusFor(id);
  current[status] = !current[status];
  tracker[id] = current;
  saveTracker();
  render();
}
function populateFamilies() {
  [...new Set(jobs.map(j => j.family))].sort().forEach(family => {
    const option = document.createElement("option"); option.value = family; option.textContent = family; $("family").append(option);
  });
}
function filteredJobs() {
  const query = $("search").value.trim().toLowerCase();
  return jobs.filter(job => {
    const personal = statusFor(job.id);
    const haystack = `${job.title} ${job.company} ${job.description} ${(job.skills || []).join(" ")}`.toLowerCase();
    return (!query || haystack.includes(query)) && (!$("family").value || job.family === $("family").value)
      && (!$("mode").value || job.work_mode.toLowerCase().includes($("mode").value))
      && (!$("status").value || personal[$("status").value])
      && ($("status").value === "hidden" || !personal.hidden);
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
    $("updated").textContent=payload.generated_at ? `Updated ${prettyDate(payload.generated_at)}` : "Run the fetcher to begin"; render();
  } catch (error) { $("result-count").textContent="Could not load jobs. Start a local web server; see README."; }
}
controls.forEach(control => control.addEventListener("input", render));
$("export").addEventListener("click", exportCsv);
boot();

