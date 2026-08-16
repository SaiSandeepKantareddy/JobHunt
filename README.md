# Personal Job Radar

A free, keyless job-discovery pipeline tailored to a senior AI/ML systems profile. It finds fresh roles every day, ranks them deterministically, and publishes a small dashboard. Your laptop can be off while GitHub Actions runs it.

**Live dashboard:** <https://saisandeepkantareddy.github.io/JobHunt/>  
**Repository:** <https://github.com/SaiSandeepKantareddy/JobHunt>

## What it solves now

- Searches millions of direct career-page postings through the public FreeHire API.
- Targets senior/staff AI engineering, ML systems, GenAI/LLM, RAG/retrieval, agentic AI, AI platform, and applied-science roles.
- Keeps Texas, California, and Washington on-site/hybrid roles plus remote US/North America roles.
- Remembers every previously surfaced job in `data/seen.json`, so a role that disappears and returns is not announced as new again.
- Explains each score using matching role and skill terms—no mystery AI judgment.
- Gives you a daily Markdown digest, searchable dashboard, CSV export, and browser-local Saved/Applied/Hidden buttons.
- Uses no LLM, paid service, API key, server, or browser bot.

It intentionally does **not** auto-submit applications. Blind submission is unreliable, can send bad answers, and risks violating job-board rules. This version removes the discovery bottleneck and takes you directly to the employer application. Autofill is the next safe layer.

## Run it now

Requires Python 3.10+ and no packages.

```bash
python3 job_digest.py
python3 -m http.server 8000
```

Open <http://localhost:8000>. The shortlist is also readable in `DAILY_DIGEST.md`.

## Make it run while your laptop is off

1. Create a GitHub repository. Public is simplest for free Actions and free Pages; do not add your résumé or personal details.
2. Push these files to the repository's default branch.
3. In **Actions**, open **Refresh job radar** and click **Run workflow** once.
4. In **Settings → Pages**, choose **Deploy from a branch**, your default branch, and `/ (root)`.
5. Bookmark the Pages URL. The workflow refreshes daily at 23:15 UTC.

GitHub may require enabling workflow write access under **Settings → Actions → General → Workflow permissions**. Scheduled workflows run only from the default branch. GitHub can disable schedules in public repositories after long inactivity, so visit or commit periodically.

For a private repository, the Actions workflow still works within GitHub's included quota, but free GitHub Pages availability depends on your plan. You can always read `DAILY_DIGEST.md` directly in GitHub.

## Tune the search

Edit `config.json`:

- `searches`: queries sent to FreeHire.
- `api_filters`: documented FreeHire facets such as seniority, region, category, and recency.
- `onsite_locations`: places you can commute to.
- `onsite_state_codes`: US state abbreviations accepted for relocation.
- `remote_regions`: remote eligibility areas to retain.
- `title_terms`, `strong_skills`, `supporting_skills`: deterministic ranking vocabulary.
- `excluded_title_terms`: obvious mismatches to discard.
- `minimum_score`: raise it for fewer, stronger matches.

The initial profile was distilled from the supplied résumé, but the repository contains only career-search keywords—no name, email, phone, employer history, or résumé file.

## Daily routine

1. Open the dashboard or `DAILY_DIGEST.md`.
2. Review the new, highest-scoring roles first.
3. Confirm location/visa eligibility on the employer page.
4. Save or hide quickly; mark a role Applied after submitting.
5. Export the visible shortlist when you want a backup.

Saved/Applied/Hidden state lives only in that browser's `localStorage`; it is not committed to GitHub and will not sync between devices. Use a private repository or a later database integration if you want a private synchronized tracker.

The seen-job ledger is different: `data/seen.json` contains only public job IDs and timestamps. GitHub Actions commits it after every run, allowing the automation to remember jobs across days without storing any of your personal application decisions.

## Social posts from hiring managers

FreeHire includes some community sources such as Telegram, but it does not provide comprehensive LinkedIn or X/Twitter manager-post search. Those platforms restrict automated access and should not be scraped with logged-in browser sessions.

A safe future `social leads` lane can ingest user-owned RSS/search-alert feeds, public community feeds, and manually shared post URLs. It should remain separate from verified vacancies because a manager saying “my team is hiring” may not include an active application link, location, or complete requirements.

## Accuracy and safety limits

- A job can be stale, duplicated, misclassified, or geographically ambiguous. Always verify the employer page.
- “Remote North America” does not guarantee US work authorization; the dashboard labels this for verification.
- FreeHire is an external open-source dependency. If its hosted API changes or is unavailable, the workflow preserves the previous successful shortlist rather than replacing it with empty data.
- Deterministic keyword matching is transparent and free, but it cannot understand every nuance of a role.
- Never commit a résumé, `.env`, credentials, DOB, address, or application answers. PDFs and common secret files are ignored by default.

## Test

```bash
python3 -m unittest discover -s tests -v
```

## Roadmap after this first win

1. Review one week of results and tune false positives/negatives.
2. Add a private synced application tracker (optional free database).
3. Add human-approved browser autofill for repetitive fields.
4. Add per-job résumé bullet suggestions using a local model or optional provider.
5. Add referral/company-contact discovery separately, with clear consent and rate limits.

The right sequence is discovery → triage → autofill → tailoring → tracking. Fully autonomous submission comes last, only for sites that allow it and only after the answers can be verified.

## Data source

[FreeHire](https://github.com/strelov1/freehire) is MIT-licensed and exposes a [public, keyless API](https://freehire.me/docs/api). Listings link back to original employer or ATS pages.
