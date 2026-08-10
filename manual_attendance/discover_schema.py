"""Print public tables/columns that look related to deployments and users."""

from __future__ import annotations

from db import get_connection


def main() -> None:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            tables = [r[0] for r in cur.fetchall()]
            print("TABLES:")
            for t in tables:
                print(f"  - {t}")

            cur.execute(
                """
                SELECT table_name, column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND (
                    column_name ILIKE '%user%'
                    OR column_name ILIKE '%deploy%'
                    OR column_name ILIKE '%enroll%'
                    OR column_name ILIKE '%learner%'
                    OR column_name ILIKE '%member%'
                    OR column_name ILIKE '%label%'
                    OR column_name ILIKE '%student%'
                    OR column_name ILIKE '%cohort%'
                  )
                ORDER BY table_name, ordinal_position
                """
            )
            print("\nRELEVANT COLUMNS:")
            for table_name, column_name, data_type in cur.fetchall():
                print(f"  {table_name}.{column_name} ({data_type})")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
