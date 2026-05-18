"""CLI entry point for administrative commands.

Usage:
    python -m app.cli import-goals <file.tsv>
"""

import argparse
import sys
from pathlib import Path

from app.config import ORG_NAME
from app.database import SessionLocal
from app.services.import_service import import_goals_from_tsv


def cmd_import_goals(args: argparse.Namespace) -> None:
    """Import goals from a TSV file exported from GitHub Projects."""
    tsv_path = Path(args.file)

    if not tsv_path.exists():
        print(f"Fout: Bestand niet gevonden: {tsv_path}")
        sys.exit(1)

    if not tsv_path.suffix.lower() == ".tsv":
        print(f"Waarschuwing: Bestand heeft geen .tsv extensie: {tsv_path}")

    print(f"Importeren van doelen uit: {tsv_path}")
    print("-" * 50)

    db = SessionLocal()
    try:
        result = import_goals_from_tsv(db, tsv_path)
        db.commit()

        print(f"Entiteiten aangemaakt:  {result.entities_created}")
        if result.entities_created_names:
            for name in result.entities_created_names:
                print(f"  + {name}")
        print(f"Entiteiten gezien:      {result.entities_seen}")
        print(f"Doelen aangemaakt:      {result.goals_created}")
        print(f"Doelen bijgewerkt:      {result.goals_updated}")
        print(f"Ouder-koppelingen:      {result.parent_links_set}")

        if result.warnings:
            print(f"\nWaarschuwingen ({len(result.warnings)}):")
            for warning in result.warnings:
                print(f"  - {warning}")

        print("-" * 50)
        print("Import voltooid.")
    finally:
        db.close()


def main() -> None:
    """Main CLI entry point with subcommands."""
    parser = argparse.ArgumentParser(description=f"{ORG_NAME} Goal Review - CLI beheercommando's")
    subparsers = parser.add_subparsers(dest="command", help="Beschikbare commando's")

    # import-goals subcommand
    import_parser = subparsers.add_parser(
        "import-goals", help="Importeer doelen vanuit een GitHub Projects TSV export"
    )
    import_parser.add_argument("file", help="Pad naar het TSV-bestand")
    import_parser.set_defaults(func=cmd_import_goals)

    args = parser.parse_args()

    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
