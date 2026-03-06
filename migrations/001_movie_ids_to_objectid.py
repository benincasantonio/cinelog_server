"""Migration 001: Convert string _id and movieId values to ObjectId.

This migration addresses a data type inconsistency where _id values in the
movies collection and movieId foreign keys in logs and movie_ratings collections
were stored as strings instead of ObjectIds.

Since the string values are valid 24-character hex ObjectId strings, we can
directly convert them to ObjectId values without generating new IDs.
"""

from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from bson import ObjectId


def up(db: Database, dry_run: bool = False) -> None:
    """Convert string _id and movieId values to ObjectId.

    This migration:
    1. Converts movies._id from string to ObjectId (same value)
    2. Converts logs.movieId from string to ObjectId (same value)
    3. Converts movie_ratings.movieId from string to ObjectId (same value)

    The movies collection requires a delete+reinsert since _id is immutable.
    The logs and movie_ratings collections use $toObjectId for efficient bulk updates.

    Args:
        db: MongoDB database instance
        dry_run: If True, only print what would be done without applying changes
    """
    print("  [001] Converting movies._id from string to ObjectId...")
    _convert_movies_ids(db, dry_run=dry_run)

    print("  [001] Converting logs.movieId from string to ObjectId...")
    _convert_logs_movie_ids(db, dry_run=dry_run)

    print("  [001] Converting movie_ratings.movieId from string to ObjectId...")
    _convert_movie_ratings_movie_ids(db, dry_run=dry_run)


def _convert_movies_ids(db: Database, dry_run: bool = False) -> None:
    """Convert _id values in movies collection from string to ObjectId.

    Since _id is immutable in MongoDB, we need to:
    1. Find all documents with string _id
    2. For each, insert a copy with ObjectId _id
    3. Delete the original string _id document

    Args:
        db: MongoDB database instance
        dry_run: If True, only report without applying changes
    """
    movies_collection = db.movies

    # Find all movies with string _id
    string_id_movies = list(
        movies_collection.find({"_id": {"$type": "string"}}, projection=None)
    )

    if not string_id_movies:
        print("    [001] No movies with string _id found")
        return

    print(f"    [001] Found {len(string_id_movies)} movie(s) with string _id")

    if dry_run:
        print("    [dry-run] Would convert movie IDs:")
        for movie_doc in string_id_movies[:10]:  # Show first 10
            old_id = movie_doc["_id"]
            print(f"      - {old_id} -> ObjectId('{old_id}')")
        if len(string_id_movies) > 10:
            print(f"      ... and {len(string_id_movies) - 10} more")
        return

    converted_count = 0
    for movie_doc in string_id_movies:
        old_id = movie_doc["_id"]

        try:
            new_id = ObjectId(old_id)
        except Exception as e:
            print(
                f"    [001] Skipping movie with invalid ObjectId string '{old_id}': {e}"
            )
            continue

        # Check if ObjectId version already exists (could happen if partially migrated)
        existing = movies_collection.find_one({"_id": new_id})
        if existing:
            print(
                f"    [001] ObjectId version already exists for '{old_id}', deleting string version"
            )
            movies_collection.delete_one({"_id": old_id})
            continue

        # Prepare the new document
        new_doc = movie_doc.copy()
        new_doc["_id"] = new_id

        # Use transaction to ensure atomic delete+insert
        try:
            with db.client.start_session() as session:
                with session.start_transaction():
                    movies_collection.delete_one({"_id": old_id}, session=session)
                    movies_collection.insert_one(new_doc, session=session)
                    converted_count += 1
        except DuplicateKeyError as e:
            print(f"    [001] DuplicateKeyError for movie '{old_id}': {e}")
            continue
        except Exception as e:
            print(f"    [001] Error converting movie '{old_id}': {e}")
            continue

    print(f"    [001] Converted {converted_count} movie(s) from string _id to ObjectId")


def _convert_logs_movie_ids(db: Database, dry_run: bool = False) -> None:
    """Convert movieId values in logs collection from string to ObjectId.

    Uses aggregation pipeline with $toObjectId for efficient bulk conversion.

    Args:
        db: MongoDB database instance
        dry_run: If True, only report without applying changes
    """
    logs_collection = db.logs

    # Check if any logs have string movieId
    string_count = logs_collection.count_documents({"movieId": {"$type": "string"}})

    if string_count == 0:
        print("    [001] No logs with string movieId found")
        return

    print(f"    [001] Found {string_count} log(s) with string movieId")

    if dry_run:
        print("    [dry-run] Would convert log movieId references using $toObjectId")
        return

    # Use aggregation pipeline to convert string movieId to ObjectId
    result = logs_collection.update_many(
        {"movieId": {"$type": "string"}},
        [{"$set": {"movieId": {"$toObjectId": "$movieId"}}}],
    )

    print(
        f"    [001] Converted {result.modified_count} log(s) from string movieId to ObjectId"
    )


def _convert_movie_ratings_movie_ids(db: Database, dry_run: bool = False) -> None:
    """Convert movieId values in movie_ratings collection from string to ObjectId.

    Uses aggregation pipeline with $toObjectId for efficient bulk conversion.

    Args:
        db: MongoDB database instance
        dry_run: If True, only report without applying changes
    """
    movie_ratings_collection = db.movie_ratings

    # Check if any movie_ratings have string movieId
    string_count = movie_ratings_collection.count_documents(
        {"movieId": {"$type": "string"}}
    )

    if string_count == 0:
        print("    [001] No movie_ratings with string movieId found")
        return

    print(f"    [001] Found {string_count} movie_rating(s) with string movieId")

    if dry_run:
        print(
            "    [dry-run] Would convert movie_rating movieId references using $toObjectId"
        )
        return

    # Use aggregation pipeline to convert string movieId to ObjectId
    result = movie_ratings_collection.update_many(
        {"movieId": {"$type": "string"}},
        [{"$set": {"movieId": {"$toObjectId": "$movieId"}}}],
    )

    print(
        f"    [001] Converted {result.modified_count} movie_rating(s) from string movieId to ObjectId"
    )


def down(db: Database) -> None:
    """No-op rollback for migration 001.

    This migration converts string IDs to ObjectId for data consistency.
    Rollback is not supported as this is a one-way data cleanup.
    """
    print("  [001] Migration 001 does not support rollback")
    print("  [001] This is a data type correction that should not be reversed")
