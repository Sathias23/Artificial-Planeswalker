#!/usr/bin/env python3
"""Quick test to verify Scryfall API connection."""

import asyncio
import sys

from src.data.importers.scryfall_api import fetch_bulk_data_list


async def main() -> int:
    """Test fetching bulk data list."""
    try:
        print("Testing Scryfall API connection...")
        bulk_data = await fetch_bulk_data_list()

        print(f"\nSuccessfully fetched {len(bulk_data)} bulk data entries:")
        for entry in bulk_data:
            print(
                f"  - {entry['type']}: {entry.get('size', 0) / (1024 * 1024):.1f} MB "
                f"(updated: {entry.get('updated_at', 'unknown')})"
            )

        return 0

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
