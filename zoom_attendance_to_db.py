import os
import uuid
import requests
import psycopg2
import urllib.parse
from datetime import datetime, timedelta, timezone

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

DB_CONFIG = {
    "host": os.environ["HOST"],
    "port": int(os.environ.get("PORT", 5432)),
    "dbname": os.environ["DBNAME"],
    "user": os.environ["USER"],
    "password": os.environ["PASSWORD"],
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
# USER LOOKUP
# =====================================================

def get_internal_user_id(cur, email):

    cur.execute(
        """
        SELECT id
        FROM public.users
        WHERE LOWER(email)=LOWER(%s)
        LIMIT 1
        """,
        (email,),
    )

    row = cur.fetchone()

    if row:
        return row[0]

    return None

# =====================================================
# MAIN
# =====================================================

def main():

    token = get_zoom_token()

    users = fetch_users(token)

    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    processed_sessions = set()
    seen_rows = set()

    inserted_rows = 0
    skipped_rows = 0

    check_sql = """
    SELECT 1
    FROM public.attendance
    WHERE user_id=%s
      AND meeting_id=%s
      AND joined_at=%s
      AND left_at=%s
    LIMIT 1;
    """

    insert_sql = """
    INSERT INTO public.attendance
    (
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
    VALUES
    (
        %s,%s,%s,%s,%s,%s,%s,%s,%s
    );
    """

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

                cur.execute(
                    check_sql,
                    (
                        user_identifier,
                        meeting_uuid,
                        join_time,
                        leave_time,
                    ),
                )

                if cur.fetchone():

                    skipped_rows += 1

                    continue

                cur.execute(
                    insert_sql,
                    (
                        str(uuid.uuid4()),
                        user_identifier,
                        meeting_uuid,
                        join_time,
                        leave_time,
                        topic,
                        start_time,
                        end_time,
                        ZOOM_ACCOUNT[
                            "zoom_account_id"
                        ],
                    ),
                )

                inserted_rows += 1
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
