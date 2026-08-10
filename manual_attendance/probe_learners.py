"""Probe users columns and learner counts via progress join."""

from __future__ import annotations

from db import get_connection


def main() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                ORDER BY ordinal_position
                """
            )
            print("USERS COLUMNS:")
            for name, dtype in cur.fetchall():
                print(f"  {name} ({dtype})")

            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'deployments'
                ORDER BY ordinal_position
                """
            )
            print("\nDEPLOYMENTS COLUMNS:")
            for name, dtype in cur.fetchall():
                print(f"  {name} ({dtype})")

            cur.execute(
                """
                SELECT DISTINCT
                    u.id,
                    COALESCE(
                        NULLIF(TRIM(CONCAT(COALESCE(u.first_name, ''), ' ', COALESCE(u.last_name, ''))), ''),
                        NULLIF(TRIM(u.email), ''),
                        u.id
                    ) AS display_name
                FROM progress p
                JOIN deployments d ON d.id = p.deployment_id
                JOIN deployment_labels dl ON dl.deployment_id = d.id
                JOIN users u ON u.id = p.user_id
                WHERE d.start_timestamp >= CURRENT_DATE - INTERVAL '3 months'
                  AND (d.intent IS NULL OR d.intent = 'Learning')
                LIMIT 5
                """
            )
            print("\nSAMPLE LEARNERS:")
            for row in cur.fetchall():
                print(f"  {row}")

            cur.execute(
                """
                SELECT l.text, COUNT(DISTINCT p.user_id) AS learner_count
                FROM labels l
                JOIN deployment_labels dl ON dl.label_id = l.id
                JOIN deployments d ON d.id = dl.deployment_id
                JOIN progress p ON p.deployment_id = d.id
                WHERE d.start_timestamp >= CURRENT_DATE - INTERVAL '3 months'
                  AND (d.intent IS NULL OR d.intent = 'Learning')
                GROUP BY l.text
                ORDER BY learner_count DESC
                LIMIT 15
                """
            )
            print("\nTOP PROGRAMS BY LEARNERS:")
            for text, count in cur.fetchall():
                print(f"  {count:4d}  {text}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
