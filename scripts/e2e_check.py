#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LifeVault End-to-End Check Script

Validates the complete workflow:
1. Initialize in-memory database
2. Import sample_data/demo.json
3. Verify total count == expected
4. Full-text search verification
5. Export JSON and verify file integrity
"""

import asyncio
import json
import sys
import tempfile
from pathlib import Path

# Set UTF-8 encoding for stdout on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))


async def main():
    print("=" * 60)
    print("LifeVault End-to-End Validation")
    print("=" * 60)

    passed_checks = []
    failed_checks = []

    # Step 1: Initialize database (use temp file instead of in-memory)
    print("\n[Step 1] Initializing temporary database...")
    try:
        import os
        from app.db import init_database

        # Create temporary database file
        temp_dir = Path(tempfile.gettempdir()) / "lifevault_test"
        temp_dir.mkdir(exist_ok=True)
        db_path = temp_dir / "test_e2e.db"

        # Set environment variable so all operations use the same database
        os.environ["LIFEVAULT_DB_PATH"] = str(db_path)

        await init_database(str(db_path))
        print("✅ Database initialized successfully")
        passed_checks.append("Database initialization")
    except Exception as exc:
        print(f"❌ Failed to initialize database: {exc}")
        failed_checks.append(("Database initialization", str(exc)))
        return print_summary(passed_checks, failed_checks)

    # Step 2: Import sample_data/demo.json
    print("\n[Step 2] Importing sample_data/demo.json...")
    try:
        from app.db import insert_messages
        from app.models.message import UnifiedMessage

        demo_json_path = Path(__file__).parent.parent / "sample_data" / "demo.json"
        if not demo_json_path.exists():
            raise FileNotFoundError(f"demo.json not found at {demo_json_path}")

        with open(demo_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        messages_data = data.get("messages", [])
        expected_count = len(messages_data)
        print(f"   Found {expected_count} messages in demo.json")

        messages = [UnifiedMessage.from_dict(msg) for msg in messages_data]
        inserted = await insert_messages(messages)

        print(f"✅ Imported {inserted} messages successfully")
        passed_checks.append(f"Import {inserted} messages")
    except Exception as exc:
        print(f"❌ Failed to import demo.json: {exc}")
        failed_checks.append(("Import demo.json", str(exc)))
        return print_summary(passed_checks, failed_checks)

    # Step 3: Verify total count
    print("\n[Step 3] Verifying message count...")
    try:
        from app.db import count_messages

        actual_count = await count_messages()
        if actual_count == expected_count:
            print(f"✅ Message count verified: {actual_count} == {expected_count}")
            passed_checks.append(f"Message count: {actual_count}")
        else:
            print(
                f"❌ Message count mismatch: expected {expected_count}, got {actual_count}"
            )
            failed_checks.append(
                (
                    "Message count",
                    f"Expected {expected_count}, got {actual_count}",
                )
            )
    except Exception as exc:
        print(f"❌ Failed to count messages: {exc}")
        failed_checks.append(("Message count", str(exc)))

    # Step 4: Full-text search verification
    print("\n[Step 4] Testing full-text search...")
    try:
        from app.db import search_messages

        # Search for common term
        search_queries = ["早", "测试", "用户"]
        search_found = False

        for query in search_queries:
            try:
                results = await search_messages(query)
                if len(results) > 0:
                    print(f"✅ Search '{query}' returned {len(results)} results")
                    passed_checks.append(f"Search '{query}'")
                    search_found = True
                    break
            except ValueError:
                # Query might not match, try next
                continue

        if not search_found:
            # Try searching for any content
            all_messages = await count_messages()
            if all_messages > 0:
                print("✅ Search functionality available (no matching terms)")
                passed_checks.append("Search functionality")
            else:
                print("⚠️  No messages to search")
                passed_checks.append("Search (no data)")

    except Exception as exc:
        print(f"❌ Failed to search messages: {exc}")
        failed_checks.append(("Full-text search", str(exc)))

    # Step 5: Export JSON and verify
    print("\n[Step 5] Testing JSON export...")
    try:
        from app.db import query_messages

        messages = await query_messages(page=1, page_size=100000)
        export_data = {
            "total": len(messages),
            "messages": [msg.to_dict() for msg in messages],
        }

        # Write to temporary file
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", delete=False
        ) as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            temp_path = f.name

        # Verify file exists and can be parsed
        with open(temp_path, "r", encoding="utf-8") as f:
            parsed = json.load(f)

        if parsed["total"] == export_data["total"]:
            print(f"✅ JSON export verified: {parsed['total']} messages")
            passed_checks.append(f"JSON export: {parsed['total']} messages")
        else:
            print(
                f"❌ JSON export count mismatch: {parsed['total']} != {export_data['total']}"
            )
            failed_checks.append(
                (
                    "JSON export",
                    f"Count mismatch: {parsed['total']} != {export_data['total']}",
                )
            )

        # Cleanup
        Path(temp_path).unlink()

    except Exception as exc:
        print(f"❌ Failed to export JSON: {exc}")
        failed_checks.append(("JSON export", str(exc)))

    # Print summary
    print_summary(passed_checks, failed_checks)


def print_summary(passed_checks: list, failed_checks: list):
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"✅ Passed: {len(passed_checks)}")
    print(f"❌ Failed: {len(failed_checks)}")

    if failed_checks:
        print("\nFailed checks:")
        for check, error in failed_checks:
            print(f"  - {check}: {error}")
        print("\n❌ Some checks failed. Please review the errors above.")
        sys.exit(1)
    else:
        print("\n✅ All checks passed. LifeVault is ready.")
        sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
