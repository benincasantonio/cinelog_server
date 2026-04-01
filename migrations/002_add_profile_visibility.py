"""Migration 002: Add profileVisibility field to existing users.

Adds a ``profileVisibility`` field with value ``"private"`` to all user
documents that do not already have the field set.
"""

from pymongo.database import Database


def up(db: Database, dry_run: bool = False) -> None:
    users_collection = db.users

    missing_count = users_collection.count_documents(
        {"profileVisibility": {"$exists": False}}
    )

    if missing_count == 0:
        print("  [002] All users already have profileVisibility field")
        return

    print(f"  [002] Found {missing_count} user(s) without profileVisibility")

    if dry_run:
        print(
            "    [dry-run] Would set profileVisibility='private' "
            f"on {missing_count} user(s)"
        )
        return

    result = users_collection.update_many(
        {"profileVisibility": {"$exists": False}},
        {"$set": {"profileVisibility": "private"}},
    )

    print(
        f"    [002] Set profileVisibility='private' on {result.modified_count} user(s)"
    )


def down(db: Database) -> None:
    users_collection = db.users

    result = users_collection.update_many(
        {"profileVisibility": {"$exists": True}},
        {"$unset": {"profileVisibility": ""}},
    )

    print(f"  [002] Removed profileVisibility from {result.modified_count} user(s)")
