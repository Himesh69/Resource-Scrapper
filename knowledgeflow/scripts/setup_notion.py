"""
KnowledgeFlow — Notion Workspace Setup Script

This script creates all 5 required Notion databases inside a page you specify.
Run it ONCE after setting up your Notion integration.

Prerequisites:
  1. Create a Notion integration:
       https://www.notion.so/my-integrations → "+ New integration"
  2. Set NOTION_TOKEN in your .env file (or pass as env var)
  3. Create a blank Notion page where the databases will live.
     Share it with your integration (click "..." on the page → Add connections)
  4. Copy the page ID from the URL:
       https://notion.so/<workspace>/<PAGE_ID_HERE>?v=...
     The page ID is the 32-char hex string (with or without dashes).

Usage:
  python scripts/setup_notion.py --page-id <your-notion-page-id>

After running, copy the printed database IDs into your .env file.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

# Add parent directory to path so we can import config
sys.path.insert(0, str(Path(__file__).parent.parent))


def normalize_page_id(raw_id: str) -> str:
    """Strip dashes and whitespace, return clean 32-char hex ID."""
    clean = re.sub(r"[\s\-]", "", raw_id.strip())
    if len(clean) != 32:
        raise ValueError(
            f"Invalid Notion page ID '{raw_id}'. "
            "Expected a 32-character hex string from the page URL."
        )
    return clean


def create_databases(page_id: str, token: str) -> dict[str, str]:
    """
    Creates all 5 KnowledgeFlow databases inside the given Notion page.
    Returns a dict mapping database name → database ID.
    """
    from notion_client import Client

    client = Client(auth=token)
    created: dict[str, str] = {}
    parent = {"type": "page_id", "page_id": page_id}

    # ── 1. Sources ────────────────────────────────────────────
    print("  Creating Sources database...")
    sources_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "📥 Sources"}}],
        properties={"Name": {"title": {}}}
    )
    client.databases.update(
        database_id=sources_db["id"],
        properties={
            "Name": {"name": "Title"},
            "URL": {"url": {}},
            "Platform": {
                "select": {
                    "options": [
                        {"name": "Instagram", "color": "pink"},
                        {"name": "YouTube", "color": "red"},
                        {"name": "X / Twitter", "color": "gray"},
                        {"name": "LinkedIn", "color": "blue"},
                        {"name": "PDF", "color": "orange"},
                        {"name": "Image", "color": "purple"},
                        {"name": "Text", "color": "green"},
                        {"name": "Other", "color": "default"},
                    ]
                }
            },
            "Summary": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Processing", "color": "yellow"},
                        {"name": "Completed", "color": "green"},
                        {"name": "Partial", "color": "orange"},
                        {"name": "Failed", "color": "red"},
                    ]
                }
            },
            "Tags": {"multi_select": {}},
            "Processed At": {"date": {}},
            "Job ID": {"rich_text": {}},
            "Warnings": {"rich_text": {}},
        }
    )
    created["NOTION_SOURCES_DB_ID"] = sources_db["id"]
    print(f"    ✅ Sources: {sources_db['id']}")

    # ── 2. Resources ──────────────────────────────────────────
    print("  Creating Resources database...")
    resources_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "🔗 Resources"}}],
        properties={"Name": {"title": {}}}
    )
    client.databases.update(
        database_id=resources_db["id"],
        properties={
            "Type": {
                "select": {
                    "options": [
                        {"name": "Website", "color": "blue"},
                        {"name": "GitHub Repository", "color": "gray"},
                        {"name": "Documentation", "color": "purple"},
                        {"name": "Book", "color": "orange"},
                        {"name": "Research Paper", "color": "yellow"},
                        {"name": "Course", "color": "green"},
                        {"name": "AI Tool", "color": "pink"},
                        {"name": "Framework", "color": "red"},
                        {"name": "Library", "color": "brown"},
                        {"name": "API", "color": "blue"},
                        {"name": "Company", "color": "gray"},
                        {"name": "Person", "color": "purple"},
                        {"name": "Newsletter", "color": "orange"},
                        {"name": "Podcast", "color": "yellow"},
                        {"name": "YouTube Channel", "color": "red"},
                        {"name": "Discord Community", "color": "blue"},
                        {"name": "Prompt", "color": "green"},
                        {"name": "Template", "color": "pink"},
                        {"name": "Other", "color": "default"},
                    ]
                }
            },
            "URL": {"url": {}},
            "Description": {"rich_text": {}},
            "Tags": {"multi_select": {}},
            "Enriched": {"checkbox": {}},
            "Source Title": {"rich_text": {}},
            "Added At": {"date": {}},
        }
    )
    created["NOTION_RESOURCES_DB_ID"] = resources_db["id"]
    print(f"    ✅ Resources: {resources_db['id']}")

    # ── 3. Categories ─────────────────────────────────────────
    print("  Creating Categories database...")
    categories_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "🗂️ Categories"}}],
        properties={"Name": {"title": {}}}
    )
    client.databases.update(
        database_id=categories_db["id"],
        properties={
            "Type": {
                "select": {
                    "options": [
                        {"name": "Primary", "color": "blue"},
                        {"name": "Subcategory", "color": "gray"},
                    ]
                }
            },
            "Difficulty": {
                "select": {
                    "options": [
                        {"name": "Beginner", "color": "green"},
                        {"name": "Intermediate", "color": "yellow"},
                        {"name": "Advanced", "color": "orange"},
                        {"name": "Expert", "color": "red"},
                    ]
                }
            },
        }
    )
    created["NOTION_CATEGORIES_DB_ID"] = categories_db["id"]
    print(f"    ✅ Categories: {categories_db['id']}")

    # ── 4. Creators ───────────────────────────────────────────
    print("  Creating Creators database...")
    creators_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "👤 Creators"}}],
        properties={"Name": {"title": {}}}
    )
    client.databases.update(
        database_id=creators_db["id"],
        properties={
            "Platform": {
                "select": {
                    "options": [
                        {"name": "Instagram", "color": "pink"},
                        {"name": "YouTube", "color": "red"},
                        {"name": "X / Twitter", "color": "gray"},
                        {"name": "LinkedIn", "color": "blue"},
                        {"name": "Other", "color": "default"},
                    ]
                }
            },
            "Username": {"rich_text": {}},
            "Profile URL": {"url": {}},
            "Notes": {"rich_text": {}},
        }
    )
    created["NOTION_CREATORS_DB_ID"] = creators_db["id"]
    print(f"    ✅ Creators: {creators_db['id']}")

    # ── 5. Knowledge ──────────────────────────────────────────
    print("  Creating Knowledge database...")
    knowledge_db = client.databases.create(
        parent=parent,
        title=[{"type": "text", "text": {"content": "🧠 Knowledge"}}],
        properties={"Name": {"title": {}}}
    )
    client.databases.update(
        database_id=knowledge_db["id"],
        properties={
            "Name": {"name": "Title"},
            "Summary": {"rich_text": {}},
            "Topics": {"multi_select": {}},
            "Action Items": {"rich_text": {}},
            "Tags": {"multi_select": {}},
            "Difficulty": {
                "select": {
                    "options": [
                        {"name": "Beginner", "color": "green"},
                        {"name": "Intermediate", "color": "yellow"},
                        {"name": "Advanced", "color": "orange"},
                        {"name": "Expert", "color": "red"},
                    ]
                }
            },
            "Source URL": {"url": {}},
            "Created At": {"date": {}},
        }
    )
    created["NOTION_KNOWLEDGE_DB_ID"] = knowledge_db["id"]
    print(f"    ✅ Knowledge: {knowledge_db['id']}")

    return created


def print_env_block(db_ids: dict[str, str]) -> None:
    """Print the .env block the user needs to copy."""
    print("\n" + "=" * 60)
    print("✅ All databases created! Copy these lines into your .env file:")
    print("=" * 60)
    for key, value in db_ids.items():
        print(f"{key}={value}")
    print("=" * 60)
    print("\nThen restart KnowledgeFlow and you're ready to go! 🚀")


def main() -> None:
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    parser = argparse.ArgumentParser(
        description="KnowledgeFlow — Notion Workspace Setup",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--page-id",
        required=True,
        help="The Notion page ID where databases will be created.",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Notion integration token. Defaults to NOTION_TOKEN env var.",
    )
    args = parser.parse_args()

    # Resolve token
    token = args.token or os.environ.get("NOTION_TOKEN")
    if not token:
        # Try loading from .env
        try:
            from dotenv import load_dotenv
            load_dotenv(Path(__file__).parent.parent / ".env")
            token = os.environ.get("NOTION_TOKEN")
        except ImportError:
            pass

    if not token:
        print("❌ NOTION_TOKEN not found. Set it in .env or pass --token <token>")
        sys.exit(1)

    # Normalize page ID
    try:
        page_id = normalize_page_id(args.page_id)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print(f"\n🚀 KnowledgeFlow Notion Setup")
    print(f"   Page ID : {page_id}")
    print(f"   Token   : {token[:8]}...{token[-4:]}\n")
    print("Creating databases...")

    try:
        db_ids = create_databases(page_id, token)
        print_env_block(db_ids)
    except Exception as exc:
        print(f"\n❌ Setup failed: {exc}")
        print("\nCommon causes:")
        print("  - The page ID is wrong (check the URL)")
        print("  - You forgot to share the page with your integration")
        print("  - Your NOTION_TOKEN is invalid")
        sys.exit(1)


if __name__ == "__main__":
    main()
