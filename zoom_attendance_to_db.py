import os
import uuid
import requests
import psycopg2
import urllib.parse
from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

today = datetime.now(IST).date()

FROM_DATE = (today - timedelta(days=1)).isoformat()
TO_DATE = today.isoformat()

print(f"📅 Fetching meetings from {FROM_DATE} to {TO_DATE}")

print(f"\n📅 DAILY MODE: {FROM_DATE} → {TO_DATE}")

# =====================================================
# CONFIG
# =====================================================

ZOOM_ACCOUNT = {
    "zoom_account_id": os.environ["ZOOM_ACCOUNT_ID"],
    "account_id": os.environ["ACCOUNT_ID"],
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
}

DB_CONFIG = {
    "host": os.environ["HOST"],
    "port": int(os.environ.get("PORT") or 5432),
    "dbname": os.environ["DBNAME"],
    "user": os.environ["USER"],
    "password": os.environ["PASSWORD"],
}

# =====================================================
# ZOOM AUTH
# =====================================================

def get_zoom_token():
    r = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "account_credentials",
            "account_id": ZOOM_ACCOUNT["account_id"],
        },
        auth=(ZOOM_ACCOUNT["client_id"], ZOOM_ACCOUNT["client_secret"]),
        timeout=20,
    )
    r.raise_for_status()
    return r.json()["access_token"]

# =====================================================
# ZOOM API
# =====================================================

def fetch_users(token):
    headers = {"Authorization": f"Bearer {token}"}
    users = []
    url = "https://api.zoom.us/v2/users"
    params = {"page_size": 300}

    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        users.extend(data.get("users", []))
        if data.get("next_page_token"):
            params["next_page_token"] = data["next_page_token"]
        else:
            break

    return users


def fetch_user_meetings(token, user_id):
    headers = {"Authorization": f"Bearer {token}"}
    meetings = []
    url = f"https://api.zoom.us/v2/report/users/{user_id}/meetings"
    params = {"from": FROM_DATE, "to": TO_DATE, "page_size": 300}

    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json()
        meetings.extend(data.get("meetings", []))
        if data.get("next_page_token"):
            params["next_page_token"] = data["next_page_token"]
        else:
            break

    return meetings


def fetch_participants(token, meeting_uuid):
    headers = {"Authorization": f"Bearer {token}"}
    participants = []

    encoded_uuid = urllib.parse.quote(
        urllib.parse.quote(meeting_uuid, safe=""), safe=""
    )
    url = f"https://api.zoom.us/v2/report/meetings/{encoded_uuid}/participants"
    params = {"page_size": 300}

    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 404:
            return []
        r.raise_for_status()
        data = r.json()
        participants.extend(data.get("participants", []))
        if data.get("next_page_token"):
            params["next_page_token"] = data["next_page_token"]
        else:
            break

    return participants


def get_internal_user_id(cur, email):
    cur.execute(
        "SELECT id FROM public.users WHERE LOWER(email) = LOWER(%s)",
        (email,),
    )
    row = cur.fetchone()
    return row[0] if row else None

# =====================================================
# MAIN
# =====================================================

def main():
    token = get_zoom_token()
    users = fetch_users(token)

    print(f"👤 Zoom users scanned: {len(users)}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    insert_sql = """
INSERT INTO public.attendance (
    id,
    user_id,
    meeting_id,
    joined_at,
    left_at,
    meeting_topic,
    scheduled_from,
    scheduled_to,
    zoom_account_id
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
ON CONFLICT (user_id, meeting_id, joined_at, left_at)
DO NOTHING;
"""

    processed_sessions = set()
    seen_rows = set()
    inserted_rows = 0

    for user in users:
        meetings = fetch_user_meetings(token, user["id"])
        if not meetings:
            continue

        print(f"📅 Host {user.get('email')} → {len(meetings)} meetings")

        for meeting in meetings:
            m_uuid = meeting["uuid"]

            if m_uuid in processed_sessions:
                continue
            processed_sessions.add(m_uuid)

            topic = meeting.get("topic")
            start = datetime.fromisoformat(
                meeting["start_time"].replace("Z", "+00:00")
            )
            end = start + timedelta(minutes=meeting.get("duration", 0))

            participants = fetch_participants(token, m_uuid)
            print(f"   → Session {m_uuid} | Participants: {len(participants)}")

            for p in participants:
                email = p.get("user_email")

                # ❌ SKIP if email is NULL
                if not email:
                    continue

                internal_id = get_internal_user_id(cur, email)
                user_identifier = internal_id or email

                join_time = datetime.fromisoformat(
                    p["join_time"].replace("Z", "+00:00")
                )
                leave_time = datetime.fromisoformat(
                    p["leave_time"].replace("Z", "+00:00")
                )

                dedupe_key = (
                    user_identifier,
                    m_uuid,
                    join_time,
                    leave_time,
                )

              for p in participants:

cur.execute(

                                cur.execute(
                    insert_sql,
                    (
                        str(uuid.uuid4()),
                        user_identifier,
                        m_uuid,
                        join_time,
                        leave_time,
                        topic,
                        start,
                        end,
                        ZOOM_ACCOUNT["zoom_account_id"],
                    ),
                )

                if cur.rowcount > 0:
                    inserted_rows += 1

    conn.commit()
    cur.close()
    conn.close()

    print("\n✅ Attendance ingestion completed.")
    print(f"📥 New attendance rows inserted: {inserted_rows}")
    print("♻️ Duplicate rows skipped automatically.")


if __name__ == "__main__":
    main()
