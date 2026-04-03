"""Migration 002: Add profileVisibility field to existing users.

This migration sets the ``profileVisibility`` field to ``"private"`` for all
existing user documents that do not already have the field.

New users created after this migration will have ``profileVisibility`` set
explicitly at registration time.
"""

from pymongo.database import Database


def up(db: Database, dry_run: bool = False) -> None:
    """Set profileVisibility to 'private' for all users missing the field.

    Args:
        db: MongoDB database instance
        dry_run: If True, only print what would be done without applying changes
    """
    users_collection = db.users

    missing_count = users_collection.count_documents(
        {"profileVisibility": {"$exists": False}}
    )

    print(
        f"  [002] Found {missing_count} user(s) missing the profileVisibility field"
    )

    if missing_count == 0:
        print("  [002] Nothing to do")
        return

    if dry_run:
        print(
            "  [dry-run] Would set profileVisibility='private' "
            f"for {missing_count} user(s)"
        )
        return

    result = users_collection.update_many(
        {"profileVisibility": {"$exists": False}},
        {"$set": {"profileVisibility": "private"}},
    )

    print(
        f"  [002] Updated {result.modified_count} user(s) "
        "with profileVisibility='private'"
    )


def down(db: Database) -> None:
    """Remove the profileVisibility field from all user documents.

    Args:
        db: MongoDB database instance
    """
    users_collection = db.users

    result = users_collection.update_many(
        {"profileVisibility": {"$exists": True}},
        {"$unset": {"profileVisibility": ""}},
    )

    print(
        f"  [002] Removed profileVisibility field from {result.modified_count} user(s)"
    )
