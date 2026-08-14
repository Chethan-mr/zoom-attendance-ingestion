# Manual Attendance — Setup from scratch (v2)

Use **one** GCP project and **one** Apps Script project only.

| Item | Value |
|---|---|
| GCP name | Manual Attendance |
| GCP project ID | `manual-attendance-504811` |
| GCP project number | `192839681801` |
| Apps Script | **Manual Attendance v2** |
| Chat connection | **Apps Script Deployment ID** (never HTTP `/exec`, never webhook) |

---

## Step 0 — Sync cache (GitHub)

1. Open GitHub repo `Chethan-mr/zoom-attendance-ingestion`
2. **Actions** → **Sync Manual Attendance Cache** → **Run workflow**
3. Wait until it finishes (creates/updates `data/manual_attendance_cache.json`)

---

## Step 1 — GitHub token

1. GitHub → Settings → Developer settings → Personal access tokens
2. Create a **classic** PAT with scopes: `repo` + `workflow`
3. Copy the token (you will paste it into Apps Script)

If an old token was shared in a screenshot, revoke it and create a new one.

---

## Step 2 — Open the correct Apps Script

1. Go to https://script.google.com
2. Open **Manual Attendance v2** (not the old “Manual Attendance”)
3. Delete or empty any extra files (`Cards.gs`, `Config.gs`, `Data.gs`) — keep only `Code.gs` (+ manifest)

---

## Step 3 — Paste code

1. Open `Code.gs` → Select all → Delete
2. Paste entire file from repo: `apps_script/Code.gs`
3. Save (Ctrl+S)

4. Project Settings (gear) → check **Show "appsscript.json" manifest file in editor**
5. Open `appsscript.json` → replace with repo: `apps_script/appsscript.json`
6. Save

---

## Step 4 — Link GCP project `192839681801`

1. In Apps Script → **Project Settings**
2. Under **Google Cloud Platform (GCP) Project**
3. Click **Change project**
4. Enter project number: **`192839681801`**
5. Confirm / Set project

You must see: **Project number `192839681801`**

---

## Step 5 — Script properties (set once)

Project Settings → **Script properties** → Edit:

| Property | Value |
|---|---|
| `CACHE_URL` | `https://raw.githubusercontent.com/Chethan-mr/zoom-attendance-ingestion/main/data/manual_attendance_cache.json` |
| `GITHUB_TOKEN` | your PAT from Step 1 |
| `GITHUB_REPO` | `Chethan-mr/zoom-attendance-ingestion` |

Save.

**Do not change `CACHE_URL` every time** — only the file content updates via GitHub Action.

---

## Step 6 — Authorize once

1. Editor → select function `onMessage` → Run
2. Review permissions → Allow
3. It may error (no Chat event) — that is OK; authorization is the goal

---

## Step 7 — Deploy

### Option A — Head (best for testing)

1. **Deploy** → **Test deployments**
2. Type: Google Workspace Add-on / Chat
3. Copy **Head Deployment ID** (starts with `AKfycb...`)

### Option B — Versioned (more stable)

1. **Deploy** → **New deployment** → type **Add-on**
2. Deploy → copy **Deployment ID**

---

## Step 8 — Configure Google Chat (same GCP project)

1. Open:  
   https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat?project=manual-attendance-504811  
2. Confirm top project picker = **Manual Attendance** (`manual-attendance-504811`)
3. **Configuration** tab:

| Setting | Value |
|---|---|
| App status | **LIVE - available to users** |
| App name | Manual attendance |
| Interactive features | **ON** |
| Join spaces and group conversations | **ON** |
| Connection | **Apps Script** (not HTTP) |
| Deployment ID | paste ID from Step 7 |
| Triggers | `onMessage`, `onAddedToSpace`, `onRemovedFromSpace`, `onAppCommand` |
| Visibility | your work email(s), e.g. the account you use in Chat |
| Build as Workspace add-on | **ON** (if shown) |

4. **Save**

**Do not** set HTTP endpoint to `script.google.com/.../exec`.  
**Do not** rely on Chat space webhooks for this app.

---

## Step 9 — Test (prove connection)

1. Open Google Chat as an email listed in Visibility
2. Open a **1:1 DM** with **Manual attendance** (or add app to a space)
3. Send: `ping`
4. Immediately open Apps Script **Manual Attendance v2 → Executions**

### Pass criteria

| Check | Must see |
|---|---|
| Executions | New **`onMessage`** at the same time, Status **Completed**, Deployment **Head** (or your version) |
| Chat | Reply like `Manual Attendance is online.` (not “not responding”) |

5. Then send: `hi`  
   → Program dropdown (nothing selected by default) → Next  
   → Date / topic name only / times → Next  
   → All present or mark absents → **Submit**

Topic is saved as: `{program}-ILT-{your topic}`

---

## Step 10 — If “not responding”

1. Check Executions right after messaging:
   - **No new `onMessage`** → wrong Deployment ID or wrong GCP project in Chat config. Repeat Steps 7–8.
   - **New `onMessage` Completed** but Chat still says not responding → reply format / redeploy Head ID again; confirm `appsscript.json` has `"addOns"` and `"chat"`.
2. Confirm Chat project number is **`192839681801`** (same as Apps Script).
3. Remove the app from Chat → add again → retry `ping`.

---

## What you change later (and what you don’t)

| Thing | Change every time? |
|---|---|
| `CACHE_URL` | **No** |
| `GITHUB_REPO` | **No** |
| Webhook | **Not used** |
| `Code.gs` | Only when you edit code → Save (Head picks it up) |
| Chat Deployment ID | Only if you create a **new** deployment or switch script/project |
| `GITHUB_TOKEN` | Only if revoked/expired |
