import os
import urllib.parse
from datetime import datetime, timedelta, timezone

import psycopg2
import requests

from db import get_connection, get_internal_user_id, insert_attendance

# =====================================================
# DATE RANGE (Yesterday + Today)
# =====================================================

IST = timezone(timedelta(hours=5, minutes=30))

today = datetime.now(IST).date()

FROM_DATE = (today - timedelta(days=1)).isoformat()
TO_DATE = today.isoformat()

print("=" * 70)
print("📅 Zoom Attendance Ingestion")
print(f"📆 Fetching meetings from {FROM_DATE} to {TO_DATE}")
print("=" * 70)

# =====================================================
# CONFIG
# =====================================================

ZOOM_ACCOUNT = {
    "zoom_account_id": os.environ["ZOOM_ACCOUNT_ID"],
    "account_id": os.environ["ACCOUNT_ID"],
    "client_id": os.environ["CLIENT_ID"],
    "client_secret": os.environ["CLIENT_SECRET"],
}

# =====================================================
# ZOOM AUTH
# =====================================================

def get_zoom_token():
    print("🔑 Getting Zoom access token...")

    response = requests.post(
        "https://zoom.us/oauth/token",
        params={
            "grant_type": "account_credentials",
            "account_id": ZOOM_ACCOUNT["account_id"],
        },
        auth=(
            ZOOM_ACCOUNT["client_id"],
            ZOOM_ACCOUNT["client_secret"],
        ),
        timeout=30,
    )

    response.raise_for_status()

    print("✅ Zoom token acquired")

    return response.json()["access_token"]

# =====================================================
# GET ALL USERS
# =====================================================

def fetch_users(token):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    users = []

    url = "https://api.zoom.us/v2/users"

    params = {
        "page_size": 300
    }

    while True:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        response.raise_for_status()

        data = response.json()

        users.extend(data.get("users", []))

        next_token = data.get("next_page_token")

        if next_token:
            params["next_page_token"] = next_token
        else:
            break

    print(f"👤 Total Zoom Users : {len(users)}")

    return users

# =====================================================
# GET MEETINGS
# =====================================================

def fetch_user_meetings(token, user_id):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    meetings = []

    url = f"https://api.zoom.us/v2/report/users/{user_id}/meetings"

    params = {
        "from": FROM_DATE,
        "to": TO_DATE,
        "page_size": 300,
    }

    while True:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 404:
            return []

        response.raise_for_status()

        data = response.json()

        meetings.extend(data.get("meetings", []))

        next_token = data.get("next_page_token")

        if next_token:
            params["next_page_token"] = next_token
        else:
            break

    return meetings

# =====================================================
# GET PARTICIPANTS
# =====================================================

def fetch_participants(token, meeting_uuid):

    headers = {
        "Authorization": f"Bearer {token}"
    }

    participants = []

    encoded_uuid = urllib.parse.quote(
        urllib.parse.quote(meeting_uuid, safe=""),
        safe=""
    )

    url = (
        "https://api.zoom.us/v2/report/meetings/"
        f"{encoded_uuid}/participants"
    )

    params = {
        "page_size": 300
    }

    while True:

        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=30,
        )

        if response.status_code == 404:
            return []

        response.raise_for_status()

        data = response.json()

        participants.extend(
            data.get("participants", [])
        )

        next_token = data.get("next_page_token")

        if next_token:
            params["next_page_token"] = next_token
        else:
            break

    return participants

# =====================================================
# MAIN
# =====================================================

def main():

    token = get_zoom_token()

    users = fetch_users(token)

    conn = get_connection()
    cur = conn.cursor()

    processed_sessions = set()
    seen_rows = set()

    inserted_rows = 0
    skipped_rows = 0

    for user in users:

        meetings = fetch_user_meetings(
            token,
            user["id"]
        )

        if not meetings:
            continue

        print(
            f"\n👤 Host : {user.get('email')} "
            f"({len(meetings)} meetings)"
        )

        for meeting in meetings:

            meeting_uuid = meeting["uuid"]

            if meeting_uuid in processed_sessions:
                continue

            processed_sessions.add(meeting_uuid)

            topic = meeting.get("topic", "")

            start_time = datetime.fromisoformat(
                meeting["start_time"].replace(
                    "Z",
                    "+00:00",
                )
            )

            end_time = (
                start_time +
                timedelta(
                    minutes=meeting.get(
                        "duration",
                        0,
                    )
                )
            )

            participants = fetch_participants(
                token,
                meeting_uuid,
            )

            print(
                f"   📋 {topic}"
            )

            print(
                f"   👥 Participants : {len(participants)}"
            )

            for participant in participants:

                email = participant.get(
                    "user_email"
                )

                if not email:
                    continue

                internal_user = get_internal_user_id(
                    cur,
                    email,
                )

                if internal_user:
                    user_identifier = internal_user
                else:
                    user_identifier = email

                join_time = datetime.fromisoformat(
                    participant["join_time"].replace(
                        "Z",
                        "+00:00",
                    )
                )

                leave_time = datetime.fromisoformat(
                    participant["leave_time"].replace(
                        "Z",
                        "+00:00",
                    )
                )

                memory_key = (
                    str(user_identifier),
                    meeting_uuid,
                    join_time,
                    leave_time,
                )

                if memory_key in seen_rows:
                    continue

                seen_rows.add(memory_key)

                inserted = insert_attendance(
                    cur,
                    user_id=user_identifier,
                    meeting_id=meeting_uuid,
                    joined_at=join_time,
                    left_at=leave_time,
                    meeting_topic=topic,
                    scheduled_from=start_time,
                    scheduled_to=end_time,
                    zoom_account_id=ZOOM_ACCOUNT["zoom_account_id"],
                )

                if inserted:
                    inserted_rows += 1
                else:
                    skipped_rows += 1

    conn.commit()

    print("\n" + "=" * 70)
    print("✅ ATTENDANCE INGESTION COMPLETED")
    print("=" * 70)
    print(f"📥 New attendance rows inserted : {inserted_rows}")
    print(f"♻️ Duplicate rows skipped       : {skipped_rows}")
    print("=" * 70)

    cur.close()
    conn.close()


if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        print("\n❌ Interrupted by user.")

    except requests.HTTPError as e:
        print(f"\n❌ Zoom API Error: {e}")
        raise

    except psycopg2.Error as e:
        print(f"\n❌ Database Error: {e}")
        raise

    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        raise
