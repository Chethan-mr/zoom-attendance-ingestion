import os
import uuid
import requests
import psycopg2
import urllib.parse
from datetime import datetime, timedelta, timezone

# =====================================================
# DATE RANGE (HARDCODED FOR RECOVERY)
# =====================================================
# Based on your image, we need to cover 2026-02-02.
# We use a slightly wider range to account for UTC shifts.
FROM_DATE = "2026-02-01"
TO_DATE = "2026-02-06"

print(f"\n📅 RECOVERY MODE: Fetching sessions from {FROM_DATE} to {TO_DATE}")

# =====================================================
# CONFIGURATION
# =====================================================
ZOOM_ACCOUNT = {
    "zoom_account_id": os.environ.get("ZOOM_ACCOUNT_ID"),
    "account_id": os.environ.get("ACCOUNT_ID"),
    "client_id": os.environ.get("CLIENT_ID"),
    "client_secret": os.environ.get("CLIENT_SECRET")
}

DB_CONFIG = {
    "host": os.environ.get("HOST"),
    "port": int(os.environ.get("PORT") or 5432),
    "dbname": os.environ.get("DBNAME"),
    "user": os.environ.get("USER"),
    "password": os.environ.get("PASSWORD")
}

FALLBACK_USER_ID = "ZOOM_EXTERNAL"

# =====================================================
# ZOOM AUTH & API
# =====================================================
def get_zoom_token():
    r = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "account_credentials",
            "account_id": ZOOM_ACCOUNT["account_id"]
        },
        auth=(ZOOM_ACCOUNT["client_id"], ZOOM_ACCOUNT["client_secret"]),
        timeout=20
    )
    r.raise_for_status()
    return r.json()["access_token"]

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
    # Double encoding is required for UUIDs that contain slashes or plus signs
    encoded_uuid = urllib.parse.quote(urllib.parse.quote(meeting_uuid, safe=''), safe='')
    url = f"https://api.zoom.us/v2/report/meetings/{encoded_uuid}/participants"
    params = {"page_size": 300}
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 404: return []
        r.raise_for_status()
        data = r.json()
        participants.extend(data.get("participants", []))
        if data.get("next_page_token"):
            params["next_page_token"] = data["next_page_token"]
        else:
            break
    return participants

def get_internal_user_id(cur, email):
    if not email: return None
    cur.execute("SELECT id FROM public.users WHERE LOWER(email) = LOWER(%s)", (email,))
    row = cur.fetchone()
    return row[0] if row else None

# =====================================================
# MAIN
# =====================================================
def main():
    token = get_zoom_token()
    all_users = fetch_users(token)
    
    # We remove the "Licensed only" filter to ensure we catch all hosts
    print(f"👤 Total Zoom users found: {len(all_users)}")

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO public.attendance (
            id, user_id, meeting_id, joined_at, left_at, 
            meeting_topic, scheduled_from, scheduled_to, zoom_account_id
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT DO NOTHING
    """

    processed_uuids = set()

    for user in all_users:
        user_email = user.get('email')
        meetings = fetch_user_meetings(token, user["id"])
        
        if not meetings:
            continue

        print(f"📅 Checking Host: {user_email} ({len(meetings)} sessions found)")

        for meeting in meetings:
            m_uuid = meeting["uuid"]
            
            # Using UUID prevents skipping the second session of the same Meeting ID
            if m_uuid in processed_uuids:
                continue
            processed_uuids.add(m_uuid)

            meeting_topic = meeting.get("topic")
            start_time = datetime.fromisoformat(meeting["start_time"].replace("Z", "+00:00"))
            end_time = start_time + timedelta(minutes=meeting.get("duration", 0))

            participants = fetch_participants(token, m_uuid)
            print(f"   → Session: {m_uuid} | Participants: {len(participants)}")

            for p in participants:
                p_email = p.get("user_email")
                internal_id = get_internal_user_id(cur, p_email)
                
                cur.execute(
                    insert_sql,
                    (
                        str(uuid.uuid4()),
                        internal_id or FALLBACK_USER_ID,
                        m_uuid,  # We store UUID as the meeting_id to keep sessions separate
                        datetime.fromisoformat(p["join_time"].replace("Z", "+00:00")),
                        datetime.fromisoformat(p["leave_time"].replace("Z", "+00:00")),
                        meeting_topic,
                        start_time,
                        end_time,
                        ZOOM_ACCOUNT["zoom_account_id"]
                    )
                )

    conn.commit()
    cur.close()
    conn.close()
    print("\n✅ PROCESS COMPLETED: All unique sessions ingested.")

if __name__ == "__main__":
    main()
