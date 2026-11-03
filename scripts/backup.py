"""Copy a Task Queue SQLite database consistently, without overwriting files."""
import argparse
import json
import sqlite3
from pathlib import Path


def summary(db):
    if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
        raise ValueError("SQLite integrity check failed")
    if db.execute("PRAGMA foreign_key_check").fetchone():
        raise ValueError("SQLite foreign key check failed")
    return {
        "projects": db.execute("SELECT id, name, revision FROM projects ORDER BY id").fetchall(),
        "entities": db.execute(
            "SELECT project_id, kind, count(*) FROM entities GROUP BY project_id, kind ORDER BY project_id, kind"
        ).fetchall(),
    }


def backup(source, destination):
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise ValueError(f"Source database does not exist: {source}")
    # Exclusive creation prevents accidental replacement of an existing database.
    with destination.open("xb"):
        pass
    destination.chmod(0o600)
    try:
        with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as src:
            with sqlite3.connect(destination) as dst:
                src.backup(dst)
                result = summary(dst)
        return result
    except Exception:
        destination.unlink()
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(json.dumps(backup(args.source, args.destination), indent=2))
