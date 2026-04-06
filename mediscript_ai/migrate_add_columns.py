#!/usr/bin/env python3
"""
Migration script: Add patient_details_json, doctor_details_json to prescriptions,
and explanation to medicines. Uses raw SQL ALTER TABLE and skips columns that
already exist.
"""
import sqlite3
import sys
from pathlib import Path

# Resolve database path (same as app: sqlite:///./mediscript.db relative to project root)
SCRIPT_DIR = Path(__file__).resolve().parent
DB_PATH = SCRIPT_DIR / "mediscript.db"


def column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table using PRAGMA table_info."""
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def run_migration() -> None:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    changes = []

    # Prescriptions: caption, patient_details_json, doctor_details_json, transliterated_json
    for col in ("caption", "patient_details_json", "doctor_details_json", "transliterated_json"):
        if not column_exists(cursor, "prescriptions", col):
            cursor.execute(f"ALTER TABLE prescriptions ADD COLUMN {col} TEXT")
            changes.append(f"prescriptions.{col}")
        else:
            print(f"  (prescriptions.{col} already exists, skipping)")

    # Medicines: explanation, age_range
    for col in ("explanation", "age_range"):
        if not column_exists(cursor, "medicines", col):
            cursor.execute(f"ALTER TABLE medicines ADD COLUMN {col} TEXT")
            changes.append(f"medicines.{col}")
        else:
            print(f"  (medicines.{col} already exists, skipping)")

    conn.commit()
    conn.close()

    if changes:
        print(f"Added columns: {', '.join(changes)}")
    else:
        print("All columns already exist. No changes made.")


def main() -> int:
    if not DB_PATH.exists():
        print(f"Error: Database not found at {DB_PATH}", file=sys.stderr)
        return 1

    print(f"Migrating database at {DB_PATH}")
    try:
        run_migration()
        print("Migration completed successfully.")
        return 0
    except sqlite3.Error as e:
        print(f"Migration failed: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
