"""CLI script to build code and ticket vector indices in Chroma."""

import argparse
import sys
from pathlib import Path

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings
from app.indexing.indexer import build_code_index, build_ticket_index


def main() -> int:
    parser = argparse.ArgumentParser(
        description="BugSleuth Code and Bug Ticket Vector Indexer"
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Only re-index files whose content hash has changed since last run",
    )
    parser.add_argument(
        "--repo",
        type=str,
        default=None,
        help="Target repository path (defaults to TARGET_REPO_PATH from .env)",
    )
    parser.add_argument(
        "--tickets",
        type=str,
        default=None,
        help="Past bug tickets JSON path (defaults to data/tickets/tickets.json)",
    )
    parser.add_argument(
        "--chroma-dir",
        type=str,
        default=None,
        help="Chroma storage directory (defaults to CHROMA_DIR from .env)",
    )
    args = parser.parse_args()

    settings = get_settings()

    print("=" * 65)
    print(" BugSleuth Indexing Pipeline (AST -> Embeddings -> Chroma)")
    print("=" * 65)
    print(f"Mode               : {'Incremental' if args.incremental else 'Full Rebuild'}")
    print(f"Target Repo        : {args.repo or settings.target_repo_path}")
    print(f"Chroma Directory   : {args.chroma_dir or settings.chroma_dir}")
    print(f"Embedding Provider : {settings.embedding_provider}")
    print("=" * 65 + "\n")

    try:
        print("[1/2] Building code index from AST chunks...")
        code_summary = build_code_index(
            repo_path=args.repo,
            chroma_dir=args.chroma_dir,
            incremental=args.incremental,
            settings=settings,
        )
        print("  --> Code Index Summary:")
        print(f"      - Files scanned            : {code_summary['files_scanned']}")
        print(f"      - Files indexed            : {code_summary['files_indexed']}")
        print(f"      - Chunks embedded          : {code_summary['chunks_embedded']}")
        print(f"      - Total chunks in DB       : {code_summary['total_chunks_in_collection']}")
        print(f"      - Time taken               : {code_summary['time_taken_seconds']}s")

        print("\n[2/2] Building past tickets index...")
        ticket_summary = build_ticket_index(
            tickets_path=args.tickets,
            chroma_dir=args.chroma_dir,
            settings=settings,
        )
        print("  --> Ticket Index Summary:")
        print(f"      - Tickets indexed          : {ticket_summary['tickets_indexed']}")
        print(f"      - Total tickets in DB      : {ticket_summary['total_tickets_in_collection']}")
        print(f"      - Time taken               : {ticket_summary['time_taken_seconds']}s")

        print("\n" + "=" * 65)
        print("Indexing completed successfully!")
        print("=" * 65)
        return 0

    except Exception as exc:
        print(f"\nERROR: Indexing failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
