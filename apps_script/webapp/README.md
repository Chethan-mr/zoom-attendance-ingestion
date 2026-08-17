# Manual Attendance Web App (shareable link)

Use this instead of Google Chat. Ops open one URL in the browser.

## What you get
- Mark attendance (program, date, topic with `{program}-ILT-` prefix, times, absents)
- One **Submit** button → GitHub Action inserts present rows
- **Recent sessions** list (offline / `MANUAL-*` attendance)

## One-time setup

### 1. Refresh cache (includes recent sessions)
GitHub → Actions → **Sync Manual Attendance Cache** → Run workflow

### 2. Create Apps Script project
1. https://script.google.com → **New project** → name **Manual Attendance Web**
2. Replace `Code.gs` with `apps_script/webapp/Code.gs`
3. File → **New** → **HTML file** → name exactly `Index` → paste `apps_script/webapp/Index.html`
4. Project Settings → show `appsscript.json` → paste `apps_script/webapp/appsscript.json`

### 3. Script properties
| Property | Value |
|---|---|
| `CACHE_URL` | `https://raw.githubusercontent.com/Chethan-mr/zoom-attendance-ingestion/main/data/manual_attendance_cache.json` |
| `GITHUB_TOKEN` | classic PAT with `repo` + `workflow` |
| `GITHUB_REPO` | `Chethan-mr/zoom-attendance-ingestion` |

### 4. Authorize
Run `getBootstrap` once → Allow

### 5. Deploy as Web app
1. **Deploy → New deployment**
2. Type: **Web app**
3. Execute as: **Me**
4. Who has access: **Anyone within Mentorskool** (or your Workspace domain)
5. Deploy → copy the **Web app URL** (`.../exec`)
6. Share that link with ops

When you change code later: Deploy → Manage deployments → Edit → **New version** → Deploy (URL stays the same).

## Flow
```text
Open link → pick program → topic + times → absents → Submit
       → GitHub Action "Manual Attendance Submit"
       → rows in public.attendance (zoom_account_id = offline session)
```

Recent sessions refresh when the cache sync workflow runs (hourly / manual).
