# Manual Attendance — Google Apps Script Chat App (free)

No Cloud Run / billing needed.

Apps Script shows the Chat cards. GitHub Actions (already using your `DB` secrets) syncs programs/learners and inserts present attendance.

```text
hi  →  Apps Script cards  →  GitHub Action inserts PRESENT rows
```

## One-time setup

### 1. Sync the cache once

In GitHub → Actions → **Sync Manual Attendance Cache** → Run workflow.

This fills `data/manual_attendance_cache.json`.

### 2. Create a GitHub token for Apps Script

Create a fine-grained PAT (or classic `repo` + `workflow`) that can:

- read repo contents
- create `repository_dispatch` on this repo

### 3. Create the Apps Script project

1. Open [script.google.com](https://script.google.com) → New project
2. Rename to **Manual Attendance**
3. Create these files and paste contents from this folder:
   - `Code.gs`
   - `Cards.gs`
   - `Config.gs`
   - `Data.gs`
4. Project Settings → check **Show "appsscript.json"**
5. Replace `appsscript.json` with the file in this folder (`"chat": {}`)

### 4. Script properties

Project Settings → Script properties:

| Property | Value |
|---|---|
| `CACHE_URL` | `https://raw.githubusercontent.com/Chethan-mr/zoom-attendance-ingestion/main/data/manual_attendance_cache.json` |
| `GITHUB_TOKEN` | your PAT |
| `GITHUB_REPO` | `Chethan-mr/zoom-attendance-ingestion` |

If the repo is private, keep using the token (code already sends `Authorization`).

### 5. Deploy Apps Script

1. Deploy → New deployment
2. Type: **Add-on**
3. Description: Manual Attendance
4. Deploy → copy the **Deployment ID**

### 6. Connect Google Chat

1. Cloud Console project **Manual Attendance**
2. Google Chat API → **Configuration**
3. App name / avatar / description
4. Interactive features: ON
5. Functionality: receive 1:1 + join spaces
6. Connection settings: **Apps Script**
7. Paste the **Deployment ID**
8. Save → publish / make available to yourself / domain

### 7. Test

1. In Google Chat, add the **Manual Attendance** app to your space  
   (Apps → search app name — not the old space webhook)
2. Send: `hi`
3. Program → date → topic → times → mark absents → Submit
4. Confirm in GitHub Actions → **Manual Attendance Submit**

## Notes

- Absents are never inserted
- `zoom_account_id` is always `offline session`
- Cache refreshes hourly; run **Sync Manual Attendance Cache** anytime for fresh learners
- The old Flask/Cloud Run path is optional and not required for this flow
