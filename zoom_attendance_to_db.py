import os
import uuid
import requests
import psycopg2
import urllib.parse
from datetime import datetime, timedelta, timezone

# =====================================================
# DATE RANGE (DAILY AUTOMATION)
# =====================================================
today = datetime.now(timezone.utc).date()
yesterday = today - timedelta(days=1)

FROM_DATE = yesterday.isoformat()
TO_DATE = today.isoformat()

print(f"\n📅 Date range: {FROM_DATE} → {TO_DATE}")

# =====================================================
# CONFIGURATION (FROM GITHUB SECRETS)
# =====================================================
ZOOM_ACCOUNT = {
    "zoom_account_id": os.environ["ZOOM_ACCOUNT_ID"],
    "account_id": os.environ["ACCOUNT_ID"],
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"]
}

DB_CONFIG = {
    "host": os.environ["HOST"],
    "port": int(os.environ.get("PORT") or 5432),
    "dbname": os.environ["DBNAME"],
    "user": os.environ["USER"],
    "password": os.environ["PASSWORD"]
}

FALLBACK_USER_ID = "ZOOM_EXTERNAL"

# =====================================================
# ZOOM AUTH
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

# =====================================================
# ZOOM API FUNCTIONS
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
    params = {
        "from": FROM_DATE,
        "to": TO_DATE,
        "page_size": 300
    }

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
    """
    Fetches participants using the Meeting UUID.
    UUIDs are double-encoded to handle special characters like '/' or '+'.
    """
    headers = {"Authorization": f"Bearer {token}"}
    participants = []
    
    # Double encode the UUID (Zoom requirement for Report APIs)
    encoded_uuid = urllib.parse.quote(urllib.parse.quote(meeting_uuid, safe=''), safe='')
    url = f"https://api.zoom.us/v2/report/meetings/{encoded_uuid}/participants"
    params = {"page_size": 300}

    while True:
        r = requests.get(url, headers=headers, params=params, timeout=30)
        if r.status_code == 404:
            return [] # No participants found for this specific session
        r.raise_for_status()
        data = r.json()
        participants.extend(data.get("participants", []))
        if data.get("next_page_token"):
            params["next_page_token"] = data["next_page_token"]
        else:
            break
    return participants

# =====================================================
# DB HELPER
# =====================================================
def get_internal_user_id(cur, email):
    if not email:
        return None
    cur.execute(
        "SELECT id FROM public.users WHERE LOWER(email) = LOWER(%s)",
        (email,)
    )
    row = cur.fetchone()
    return row[0] if row else None

# =====================================================
# MAIN PROCESS
# =====================================================
def main():
    token = get_zoom_token()
    users = fetch_users(token)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    # Note: We use the meeting_uuid in the INSERT to ensure sessions 
    # of the same meeting ID don't collide.
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
        ON CONFLICT DO NOTHING
    """

    processed_uuids = set()
    licensed_users = [u for u in users if u.get("type") == 2]
    print(f"👤 Licensed users: {len(licensed_users)}")

    for user in licensed_users:
        print(f"📅 Host: {user['email']}")
        meetings = fetch_user_meetings(token, user["id"])
        print(f"   → Meetings Found: {len(meetings)}")

        for meeting in meetings:
            # Use UUID for tracking uniqueness
            m_uuid = meeting["uuid"]

            if m_uuid in processed_uuids:
                continue
            processed_uuids.add(m_uuid)

            meeting_topic = meeting.get("topic")
            
            # Use start_time and duration for scheduling info
            start_str = meeting["start_time"].replace("Z", "+00:00")
            scheduled_from = datetime.fromisoformat(start_str)
            scheduled_to = scheduled_from + timedelta(minutes=meeting.get("duration", 0))

            # Fetch participants using the unique UUID session
            participants = fetch_participants(token, m_uuid)
            print(f"      → UUID: {m_uuid} | Participants: {len(participants)}")

            for p in participants:
                email = p.get("user_email")
                internal_user_id = get_internal_user_id(cur, email)
                user_id_to_insert = internal_user_id or FALLBACK_USER_ID

                cur.execute(
                    insert_sql,
                    (
                        str(uuid.uuid4()),
                        user_id_to_insert,
                        m_uuid, # Saving UUID instead of ID ensures both meetings show up
                        datetime.fromisoformat(p["join_time"].replace("Z", "+00:00")),
                        datetime.fromisoformat(p["leave_time"].replace("Z", "+00:00")),
                        meeting_topic,
                        scheduled_from,
                        scheduled_to,
                        ZOOM_ACCOUNT["zoom_account_id"]
                    )
                )

    conn.commit()
    cur.close()
    conn.close()
    print("\n✅ DONE: Daily Zoom attendance ingestion completed (UUID logic applied)")

if __name__ == "__main__":
    main()
