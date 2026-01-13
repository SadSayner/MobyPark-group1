import sqlite3
from pathlib import Path

DB_PATH = Path("v1/Database/MobyPark.db")


def run_migration():
    if not DB_PATH.exists():
        print(" Database bestaat niet:", DB_PATH)
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON;")
        cur = conn.cursor()

        cur.execute(
            """
            SELECT DISTINCT user_id, vehicle_id
            FROM reservations
        """
        )
        user_vehicle_pairs = cur.fetchall()
        added = 0
        for user_id, vehicle_id in user_vehicle_pairs:
            cur.execute(
                """
                INSERT OR IGNORE INTO user_vehicles (user_id, vehicle_id)
                VALUES (?, ?)
            """,
                (user_id, vehicle_id),
            )
            added += cur.rowcount
        print(f"✅ {added} records toegevoegd aan user_vehicles.")

        cur.execute(
            """
            SELECT user_id
            FROM user_vehicles
            GROUP BY user_id
            HAVING COUNT(vehicle_id) > 1
        """
        )
        multi_vehicle_users = [row[0] for row in cur.fetchall()]
        print(f"Gebruikers met meerdere voertuigen: {multi_vehicle_users}")

        for user_id in multi_vehicle_users:
            company_name = f"{user_id}'s Company"
            cur.execute(
                "SELECT company_id FROM companies WHERE name = ?", (company_name,)
            )
            row = cur.fetchone()
            if row:
                company_id = row[0]
            else:
                cur.execute(
                    """
                    INSERT INTO companies (name, created_at)
                    VALUES (?, CURRENT_TIMESTAMP)
                """,
                    (company_name,),
                )
                company_id = cur.lastrowid
            cur.execute(
                """
                UPDATE user_vehicles
                SET company_id = ?
                WHERE user_id = ?
            """,
                (company_id, user_id),
            )

        conn.commit()
        print("Bedrijven aangemaakt en user_vehicles geüpdatet.")


if __name__ == "__main__":
    run_migration()
