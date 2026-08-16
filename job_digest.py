#!/usr/bin/env python3
"""Fetch and rank relevant jobs without paid services or API keys."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent
API_URL = "https://freehire.me/api/v1/agent/jobs/search"
USER_AGENT = "PersonalJobRadar/1.0 (+https://github.com/)"


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def fetch_json(url: str, timeout: int = 30) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def build_url(query: str, config: dict[str, Any], offset: int = 0) -> str:
    params: dict[str, Any] = {
        "q": query,
        "description_format": "text",
        "sort": "posted_at",
        "order": "desc",
        "limit": min(100, int(config.get("max_results_per_search", 100))),
        "offset": offset,
        **config.get("api_filters", {}),
    }
    return API_URL + "?" + urllib.parse.urlencode(params)


def normalize_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    return re.sub(r"\s+", " ", text).strip().lower()


def contains_term(text: str, term: str) -> bool:
    escaped = re.escape(term.lower()).replace(r"\ ", r"[\s\-_/]+")
    return re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", text) is not None


def matched_terms(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if contains_term(text, term)]


def classify(job: dict[str, Any]) -> str:
    text = normalize_text(f"{job.get('title', '')} {job.get('description', '')[:3000]}")
    families = [
        ("Agentic AI", ["agentic", "ai agent", "multi-agent", "langgraph"]),
        ("RAG & Retrieval", ["rag", "retrieval", "vector search", "reranking"]),
        ("GenAI / LLM", ["generative ai", "genai", "llm", "large language model"]),
        ("AI / ML Platform", ["ai platform", "ml platform", "mlops", "model serving"]),
        ("Applied Science", ["applied scientist", "research scientist"]),
    ]
    for family, terms in families:
        if any(contains_term(text, term) for term in terms):
            return family
    return "Machine Learning"


def acceptable_location(job: dict[str, Any], config: dict[str, Any]) -> tuple[bool, str]:
    location = normalize_text(job.get("location"))
    mode = normalize_text(job.get("work_mode"))
    regions = {normalize_text(x) for x in job.get("regions", [])}
    countries = {normalize_text(x) for x in job.get("countries", [])}
    local = any(normalize_text(x) in location for x in config.get("onsite_locations", []))
    us_resolved = "us" in countries or "united states" in location or re.search(r"(?:^|[,;/ ])u\.?s\.?a?(?:$|[,;/ ])", location)
    state_code_match = any(
        re.search(rf"(?:^|[,;/ ]){re.escape(code.lower())}(?:$|[,;/ ])", location)
        for code in config.get("onsite_state_codes", [])
    )
    local = local or bool(state_code_match and us_resolved)
    # A North America region includes Canada. When the source resolves countries,
    # keep only US-capable postings; unresolved generic "Remote" roles remain for
    # manual eligibility verification.
    if countries and "us" not in countries and not local:
        return False, "Outside preferred country"
    remote_region = bool(regions.intersection(config.get("remote_regions", [])))
    us_remote = mode == "remote" and ("us" in countries or remote_region or "united states" in location)
    location_says_remote = "remote" in location and ("us" in countries or remote_region or "united states" in location)
    if local:
        return True, "Target relocation market: TX, CA, or WA"
    if us_remote or location_says_remote:
        return True, "Remote US/North America — verify eligibility"
    return False, "Outside preferred area"


def update_seen_ledger(
    existing: dict[str, Any], current_ids: set[str], generated_at: str, seed_ids: Optional[set[str]] = None
) -> tuple[dict[str, Any], set[str]]:
    records = dict(existing.get("jobs", {}))
    # Migration path: when upgrading an existing installation, its last shortlist
    # was already shown and must not suddenly appear as new.
    if not records and seed_ids:
        records = {job_id: {"first_seen": generated_at, "last_seen": generated_at} for job_id in seed_ids}
    new_ids = current_ids - set(records)
    for job_id in current_ids:
        record = records.setdefault(job_id, {"first_seen": generated_at})
        record["last_seen"] = generated_at
    return {"updated_at": generated_at, "jobs": records}, new_ids


def score_job(job: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
    title = normalize_text(job.get("title"))
    body = normalize_text(job.get("description"))
    whole = f"{title} {body}"
    if any(contains_term(title, term) for term in config.get("excluded_title_terms", [])):
        return None

    title_hits = matched_terms(title, config.get("title_terms", []))
    strong_hits = matched_terms(whole, config.get("strong_skills", []))
    support_hits = matched_terms(whole, config.get("supporting_skills", []))
    location_ok, location_reason = acceptable_location(job, config)
    if not location_ok or not title_hits:
        return None

    score = min(38, 16 + 8 * len(title_hits))
    score += min(32, 5 * len(strong_hits))
    score += min(18, 2 * len(support_hits))
    seniority = [normalize_text(x) for x in job.get("seniority", [])]
    if not seniority:
        value = job.get("enrichment", {}).get("seniority")
        seniority = [normalize_text(value)] if value else []
    if {"senior", "staff", "principal", "lead"}.intersection(seniority) or re.search(r"\b(sr\.?|senior|staff|principal|lead)\b", title):
        score += 8
    score += 4
    score = min(100, score)
    if score < int(config.get("minimum_score", 36)):
        return None

    why = []
    if title_hits:
        why.append("Role match: " + ", ".join(title_hits[:3]))
    if strong_hits:
        why.append("Core match: " + ", ".join(strong_hits[:5]))
    if support_hits:
        why.append("Stack match: " + ", ".join(support_hits[:5]))
    why.append(location_reason)

    description = re.sub(r"\s+", " ", str(job.get("description") or "")).strip()
    enrichment = job.get("enrichment") or {}
    salary = job.get("salary") or enrichment.get("salary")
    return {
        "id": job.get("public_slug") or job.get("external_id") or job.get("url"),
        "title": job.get("title", "Untitled role"),
        "company": job.get("company", "Unknown company"),
        "location": job.get("location") or "Location not listed",
        "work_mode": job.get("work_mode") or enrichment.get("work_mode") or "not specified",
        "posted_at": job.get("posted_at") or job.get("created_at"),
        "url": job.get("url"),
        "source": job.get("source", "unknown"),
        "countries": job.get("countries", []),
        "regions": job.get("regions", []),
        "family": classify(job),
        "score": score,
        "why": why,
        "skills": sorted(set(str(x) for x in job.get("skills", [])))[:20],
        "description": description[:650] + ("…" if len(description) > 650 else ""),
        "experience_years_min": enrichment.get("experience_years_min"),
        "salary": salary,
    }


def fetch_jobs(config: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    raw_by_id: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for query in config.get("searches", []):
        try:
            payload = fetch_json(build_url(query, config))
            for job in payload.get("data", []):
                key = str(job.get("public_slug") or job.get("external_id") or job.get("url"))
                raw_by_id[key] = job
        except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{query}: {exc}")

    ranked = [result for job in raw_by_id.values() if (result := score_job(job, config))]
    ranked.sort(key=lambda job: (job["score"], job.get("posted_at") or ""), reverse=True)
    deduplicated: list[dict[str, Any]] = []
    seen_roles: set[tuple[str, str]] = set()
    for job in ranked:
        role_key = (normalize_text(job["company"]), normalize_text(job["title"]))
        if role_key in seen_roles:
            continue
        seen_roles.add(role_key)
        deduplicated.append(job)
    return deduplicated[: int(config.get("max_jobs", 250))], errors


def build_digest(jobs: list[dict[str, Any]], new_ids: set[str], generated_at: str, errors: list[str]) -> str:
    lines = [
        "# Daily AI/ML job shortlist",
        "",
        f"Generated: {generated_at}",
        f"Matches: **{len(jobs)}** · New since last run: **{len(new_ids)}**",
        "",
        "Open `index.html` through a web server for filters and private browser-only tracking.",
        "",
        "## Best new matches",
        "",
    ]
    best = [job for job in jobs if job["id"] in new_ids][:30]
    if not best:
        lines.append("No new matches this run.")
    for job in best:
        why = "; ".join(job["why"][:2])
        lines.extend([
            f"### {job['score']} · [{job['title']}]({job['url']}) — {job['company']}",
            "",
            f"{job['location']} · {job['family']} · {job.get('posted_at') or 'date unavailable'}  ",
            f"{why}",
            "",
        ])
    if errors:
        lines.extend(["## Source warnings", "", *[f"- {error}" for error in errors], ""])
    return "\n".join(lines) + "\n"


def run(config_path: Path, data_dir: Path) -> int:
    config = load_json(config_path, {})
    if not config.get("searches"):
        print(f"No searches configured in {config_path}", file=sys.stderr)
        return 2
    old_payload = load_json(data_dir / "jobs.json", {"jobs": []})
    old_ids = {str(job.get("id")) for job in old_payload.get("jobs", [])}
    seen_path = data_dir / "seen.json"
    seen_ledger = load_json(seen_path, {"jobs": {}})
    jobs, errors = fetch_jobs(config)
    if not jobs and errors:
        print("All searches failed; preserving existing output.", file=sys.stderr)
        for error in errors:
            print(error, file=sys.stderr)
        return 1

    generated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    current_ids = {str(job["id"]) for job in jobs}
    seen_ledger, new_ids = update_seen_ledger(seen_ledger, current_ids, generated_at, seed_ids=old_ids)
    for job in jobs:
        job["is_new"] = job["id"] in new_ids
    payload = {
        "generated_at": generated_at,
        "source": "freehire.me public API",
        "count": len(jobs),
        "new_count": len(new_ids),
        "warnings": errors,
        "jobs": jobs,
    }
    write_json(data_dir / "jobs.json", payload)
    write_json(data_dir / "new_jobs.json", {**payload, "jobs": [j for j in jobs if j["is_new"]]})
    write_json(seen_path, seen_ledger)
    (ROOT / "DAILY_DIGEST.md").write_text(build_digest(jobs, new_ids, generated_at, errors), encoding="utf-8")
    print(f"Wrote {len(jobs)} matches ({len(new_ids)} new) to {data_dir / 'jobs.json'}")
    if errors:
        print(f"Completed with {len(errors)} source warning(s).", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "config.json")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data")
    args = parser.parse_args()
    return run(args.config, args.data_dir)


if __name__ == "__main__":
    raise SystemExit(main())
