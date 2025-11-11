#!/usr/bin/env python3
"""Throwaway migration script for WKS v1 to v2.

This script migrates:
1. Config file (~/.wks/config.json) from old to new format
2. MongoDB data (add priority field to embeddings)
3. Create new collections (monitor, vault)

Run with --dry-run first to preview changes.

After successful migration, this script can be deleted.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from pymongo import MongoClient
from wks.config import load_config, wks_home_path
from wks.config_schema import is_old_config, migrate_config, validate_config
from wks.display.context import get_display, add_display_argument
from wks.priority import calculate_priority


def backup_database(client: MongoClient, db_name: str, backup_dir: Path, display) -> Path:
    """Backup a database to JSON file.

    Args:
        client: MongoDB client
        db_name: Database name to backup
        backup_dir: Directory to store backup
        display: Display instance

    Returns:
        Path to backup file
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"{db_name}_{timestamp}.json"

    db = client[db_name]
    collections = db.list_collection_names()

    backup_data = {}
    for coll_name in collections:
        coll = db[coll_name]
        docs = list(coll.find())
        # Convert ObjectId to string for JSON serialization
        for doc in docs:
            if "_id" in doc:
                doc["_id"] = str(doc["_id"])
        backup_data[coll_name] = docs

    backup_file.parent.mkdir(parents=True, exist_ok=True)
    with open(backup_file, "w") as f:
        json.dump(backup_data, f, indent=2, default=str)

    return backup_file


def migrate_config_file(dry_run: bool, display) -> Dict[str, Any]:
    """Migrate config file if needed.

    Args:
        dry_run: If True, don't write changes
        display: Display instance

    Returns:
        Dict with migration results
    """
    config_path = wks_home_path() / "config.json"

    if not config_path.exists():
        display.warning(f"Config file not found: {config_path}")
        return {"status": "not_found", "path": str(config_path)}

    # Load current config
    with open(config_path) as f:
        old_config = json.load(f)

    # Check if migration needed
    if not is_old_config(old_config):
        display.info("Config already in new format")
        return {"status": "already_migrated"}

    # Migrate
    display.status("Migrating config file...")
    new_config = migrate_config(old_config)

    # Validate
    is_valid, errors = validate_config(new_config)
    if not is_valid:
        display.error("Config validation failed", details="\n".join(errors))
        return {"status": "validation_failed", "errors": errors}

    if dry_run:
        display.info("(Dry run) Would migrate config file")
        return {"status": "would_migrate", "path": str(config_path)}

    # Backup old config
    backup_path = config_path.with_suffix(".json.backup")
    with open(backup_path, "w") as f:
        json.dump(old_config, f, indent=2)

    # Write new config
    with open(config_path, "w") as f:
        json.dump(new_config, f, indent=2)

    display.success(f"Config migrated (backup: {backup_path})")
    return {"status": "migrated", "path": str(config_path), "backup": str(backup_path)}


def add_priority_to_embeddings(
    client: MongoClient,
    config: Dict[str, Any],
    dry_run: bool,
    display
) -> Dict[str, Any]:
    """Add priority field to existing embedding documents.

    Args:
        client: MongoDB client
        config: WKS config
        dry_run: If True, don't write changes
        display: Display instance

    Returns:
        Dict with migration results
    """
    # Get similarity config
    similarity_config = config.get("similarity", {})
    if not similarity_config:
        # Try new format
        similarity_config = config.get("related", {}).get("engines", {}).get("embedding", {})

    db_name = similarity_config.get("database", "wks_similarity")
    coll_name = similarity_config.get("collection", "file_embeddings")

    db = client[db_name]
    coll = db[coll_name]

    # Count documents without priority
    docs_to_migrate = coll.count_documents({"priority": {"$exists": False}})

    if docs_to_migrate == 0:
        display.info("All embedding documents already have priority field")
        return {"status": "already_migrated", "count": 0}

    display.status(f"Found {docs_to_migrate} documents to migrate")

    if dry_run:
        display.info(f"(Dry run) Would add priority to {docs_to_migrate} documents")
        return {"status": "would_migrate", "count": docs_to_migrate}

    # Get priority config
    monitor_config = config.get("monitor", {})
    managed_dirs = monitor_config.get("managed_directories", {
        "~/Desktop": 150,
        "~/deadlines": 120,
        "~": 100,
        "~/Documents": 100,
        "~/Pictures": 80,
        "~/Downloads": 50,
    })
    priority_config = monitor_config.get("priority", {
        "depth_multiplier": 0.9,
        "underscore_divisor": 2,
        "single_underscore_divisor": 64,
        "extension_weights": {
            ".docx": 1.3,
            ".pptx": 1.3,
            ".pdf": 1.1,
            "default": 1.0
        }
    })

    # Migrate documents with progress
    progress = display.progress_start(docs_to_migrate, "Adding priority field")

    updated_count = 0
    error_count = 0

    cursor = coll.find({"priority": {"$exists": False}})
    for doc in cursor:
        try:
            file_path = Path(doc["file_path"])
            priority = calculate_priority(file_path, managed_dirs, priority_config)

            coll.update_one(
                {"_id": doc["_id"]},
                {"$set": {"priority": priority}}
            )
            updated_count += 1
            display.progress_update(progress, advance=1)
        except Exception as e:
            error_count += 1
            display.progress_update(progress, advance=1)

    display.progress_finish(progress)

    if error_count > 0:
        display.warning(f"Migrated {updated_count} documents with {error_count} errors")
    else:
        display.success(f"Added priority to {updated_count} documents")

    return {
        "status": "migrated",
        "updated": updated_count,
        "errors": error_count,
        "database": db_name,
        "collection": coll_name
    }


def create_new_collections(
    client: MongoClient,
    config: Dict[str, Any],
    dry_run: bool,
    display
) -> Dict[str, Any]:
    """Create new collections for v2 architecture.

    Args:
        client: MongoDB client
        config: WKS config
        dry_run: If True, don't create collections
        display: Display instance

    Returns:
        Dict with creation results
    """
    results = {}

    # Monitor collection
    monitor_config = config.get("monitor", {})
    monitor_db = monitor_config.get("database", "wks_monitor")
    monitor_coll = monitor_config.get("collection", "filesystem")

    if dry_run:
        display.info(f"(Dry run) Would create {monitor_db}.{monitor_coll}")
        results["monitor"] = {"status": "would_create", "db": monitor_db, "coll": monitor_coll}
    else:
        db = client[monitor_db]
        if monitor_coll not in db.list_collection_names():
            db.create_collection(monitor_coll)
            display.success(f"Created {monitor_db}.{monitor_coll}")
            results["monitor"] = {"status": "created", "db": monitor_db, "coll": monitor_coll}
        else:
            display.info(f"Collection already exists: {monitor_db}.{monitor_coll}")
            results["monitor"] = {"status": "already_exists", "db": monitor_db, "coll": monitor_coll}

    # Vault collection
    vault_config = config.get("vault", {})
    vault_db = vault_config.get("database", "wks_vault")
    vault_coll = vault_config.get("collection", "links")

    if dry_run:
        display.info(f"(Dry run) Would create {vault_db}.{vault_coll}")
        results["vault"] = {"status": "would_create", "db": vault_db, "coll": vault_coll}
    else:
        db = client[vault_db]
        if vault_coll not in db.list_collection_names():
            db.create_collection(vault_coll)
            display.success(f"Created {vault_db}.{vault_coll}")
            results["vault"] = {"status": "created", "db": vault_db, "coll": vault_coll}
        else:
            display.info(f"Collection already exists: {vault_db}.{vault_coll}")
            results["vault"] = {"status": "already_exists", "db": vault_db, "coll": vault_coll}

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Migrate WKS from v1 to v2 architecture"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without applying them"
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Execute the migration (required for actual changes)"
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / ".wks" / "backups",
        help="Directory for database backups (default: ~/.wks/backups)"
    )
    add_display_argument(parser)

    args = parser.parse_args()

    # Get display
    display = get_display(args.display)

    # Validate mode
    if not args.dry_run and not args.execute:
        display.error("Must specify --dry-run or --execute")
        display.info("Run with --dry-run first to preview changes")
        sys.exit(1)

    if args.dry_run and args.execute:
        display.error("Cannot specify both --dry-run and --execute")
        sys.exit(1)

    dry_run = args.dry_run

    # Show header
    mode = "DRY RUN" if dry_run else "EXECUTE"
    display.panel(
        f"WKS v1 → v2 Migration\nMode: {mode}\nTimestamp: {datetime.now().isoformat()}",
        title="Migration Script"
    )

    # Load config
    display.status("Loading config...")
    try:
        config = load_config()
    except Exception as e:
        display.error(f"Failed to load config: {e}")
        sys.exit(1)

    # Connect to MongoDB
    mongo_config = config.get("mongo", {})
    if not mongo_config:
        mongo_config = config.get("db", {})

    mongo_uri = mongo_config.get("uri", "mongodb://localhost:27017/")

    display.status(f"Connecting to MongoDB: {mongo_uri}")
    try:
        client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
        client.server_info()  # Force connection
        display.success("Connected to MongoDB")
    except Exception as e:
        display.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)

    # Collect results
    migration_results = {}

    # 1. Migrate config file
    display.status("\n=== Step 1: Config File Migration ===")
    migration_results["config"] = migrate_config_file(dry_run, display)

    # Reload config if migrated
    if migration_results["config"]["status"] == "migrated":
        config = load_config()

    # 2. Backup databases
    if not dry_run:
        display.status("\n=== Step 2: Database Backup ===")
        backup_dir = args.backup_dir

        # Determine which databases to backup
        db_names = set()

        # Old format databases
        if "mongo" in config:
            if "space_database" in config["mongo"]:
                db_names.add(config["mongo"]["space_database"])
            if "time_database" in config["mongo"]:
                db_names.add(config["mongo"]["time_database"])

        # New format databases
        if "related" in config:
            embedding_config = config["related"].get("engines", {}).get("embedding", {})
            if "database" in embedding_config:
                db_names.add(embedding_config["database"])

        if "similarity" in config:
            if "database" in config["similarity"]:
                db_names.add(config["similarity"]["database"])

        migration_results["backups"] = {}
        for db_name in db_names:
            try:
                backup_file = backup_database(client, db_name, backup_dir, display)
                display.success(f"Backed up {db_name} → {backup_file}")
                migration_results["backups"][db_name] = str(backup_file)
            except Exception as e:
                display.error(f"Failed to backup {db_name}: {e}")
                migration_results["backups"][db_name] = f"ERROR: {e}"

    # 3. Add priority to embeddings
    display.status("\n=== Step 3: Add Priority Field ===")
    try:
        migration_results["priority"] = add_priority_to_embeddings(
            client, config, dry_run, display
        )
    except Exception as e:
        display.error(f"Failed to add priority field: {e}")
        migration_results["priority"] = {"status": "error", "error": str(e)}

    # 4. Create new collections
    display.status("\n=== Step 4: Create New Collections ===")
    try:
        migration_results["collections"] = create_new_collections(
            client, config, dry_run, display
        )
    except Exception as e:
        display.error(f"Failed to create collections: {e}")
        migration_results["collections"] = {"status": "error", "error": str(e)}

    # Summary
    display.status("\n=== Migration Summary ===")

    summary_data = []

    # Config
    config_status = migration_results["config"]["status"]
    summary_data.append({
        "Component": "Config File",
        "Status": config_status,
        "Details": migration_results["config"].get("path", "N/A")
    })

    # Backups
    if "backups" in migration_results:
        for db_name, backup_file in migration_results["backups"].items():
            summary_data.append({
                "Component": f"Backup: {db_name}",
                "Status": "created",
                "Details": backup_file
            })

    # Priority
    priority_result = migration_results.get("priority", {})
    priority_status = priority_result.get("status", "unknown")
    priority_details = ""
    if "updated" in priority_result:
        priority_details = f"{priority_result['updated']} documents"
    elif "count" in priority_result:
        priority_details = f"{priority_result['count']} documents"

    summary_data.append({
        "Component": "Priority Field",
        "Status": priority_status,
        "Details": priority_details
    })

    # Collections
    collections_result = migration_results.get("collections", {})
    for name, info in collections_result.items():
        if isinstance(info, dict):
            summary_data.append({
                "Component": f"Collection: {name}",
                "Status": info.get("status", "unknown"),
                "Details": f"{info.get('db', '')}.{info.get('coll', '')}"
            })

    display.table(summary_data, headers=["Component", "Status", "Details"])

    # Final message
    if dry_run:
        display.info("\nDry run complete. Run with --execute to apply changes.")
    else:
        display.success("\nMigration complete!")
        display.info("You can now delete this migration script.")

    # JSON output for MCP
    if args.display == "mcp":
        display.json_output(migration_results)


if __name__ == "__main__":
    main()
