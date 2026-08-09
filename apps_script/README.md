# Manual Attendance — Google Apps Script Chat App (free)

No Cloud Run / billing needed.

**Important:** Do **not** use an Apps Script Web app URL as the Chat HTTP endpoint.  
Chat cannot follow Apps Script redirects, so you get `not responding` even when the browser works.

Use **Apps Script deployment ID** in Chat Configuration instead.

```text
hi  →  Apps Script cards  →  GitHub Action inserts PRESENT rows
```

## One-time setup

### 1. Sync the cache once

GitHub → Actions → **Sync Manual Attendance Cache** → Run workflow.

### 2. GitHub token for Apps Script

Classic PAT with `repo` + `workflow`.

### 3. Apps Script project

1. [script.google.com](https://script.google.com) → New project → name **Manual Attendance**
2. Paste files: `Code.gs`, `Cards.gs`, `Config.gs`, `Data.gs`
3. Project Settings → show `appsscript.json` → paste repo `appsscript.json`
4. Project Settings → GCP project number: `192839681801` → Set project  
   (OAuth consent screen must already be configured)

### 4. Script properties

| Property | Value |
|---|---|
| `CACHE_URL` | `https://raw.githubusercontent.com/Chethan-mr/zoom-attendance-ingestion/main/data/manual_attendance_cache.json` |
| `GITHUB_TOKEN` | your PAT |
| `GITHUB_REPO` | `Chethan-mr/zoom-attendance-ingestion` |

### 5. Authorize UrlFetch once

Run function `onMessage` once → Allow  
(`script.external_request` only — do not add `chat.bot` to oauthScopes)

### 6. Deploy as Add-on

1. Deploy → New deployment → Type: **Add-on**
2. Deploy → copy **Deployment ID**

### 7. Google Chat API Configuration

1. https://console.cloud.google.com/apis/api/chat.googleapis.com/hangouts-chat?project=manual-attendance-504811
2. Configuration tab
3. App name / avatar / description
4. Interactive features: ON
5. Receive 1:1 + join spaces: ON
6. Connection / Triggers: **Apps Script** (NOT HTTP endpoint URL)
7. Paste **Deployment ID**
8. App status: **LIVE**
9. Save

### 8. Test

1. Add **Manual attendance** app to the space
2. `@Manual attendance ping` → should reply online
3. `@Manual attendance hi` → program card

## If you still see "not responding"

1. Apps Script → **Executions** — any failed run? copy error
2. Redeploy Add-on → **New version** → update Deployment ID in Chat config → Save
3. Confirm Chat is **not** using `script.google.com/.../exec` as HTTP URL
