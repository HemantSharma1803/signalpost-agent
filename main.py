#!/usr/bin/env python3
"""Signalpost Agent — CLI entry point.

Usage:
    python main.py --org 923609016
    python main.py --bulk --count 1000
    python main.py --bulk --count 1000 --no-llm   # facts only, skip summaries
    python main.py --update                        # refresh the existing dataset
"""
import argparse
import json
import sys

from src.agent import process_one, process_bulk, process_update
from src.budget_guard import BudgetGuard


def main() -> None:
    parser = argparse.ArgumentParser(description="Signalpost company-info agent")
    parser.add_argument("--org", type=str, help="Look up a single Norwegian org number")
    parser.add_argument("--bulk", action="store_true", help="Build the full submission dataset")
    parser.add_argument("--update", action="store_true", help="Refresh the existing dataset (keeps profiles current)")
    parser.add_argument("--count", type=int, default=1000, help="How many companies to fetch in bulk mode")
    parser.add_argument("--no-llm", action="store_true", help="Skip LLM summaries (facts only)")
    args = parser.parse_args()

    if args.org:
        guard = BudgetGuard()
        profile = process_one(args.org, guard=guard, use_llm=not args.no_llm)
        print(json.dumps(profile.to_dict(), ensure_ascii=False, indent=2))
        return

    if args.update:
        process_update(use_llm=not args.no_llm)
        return

    if args.bulk:
        process_bulk(target_count=args.count, use_llm=not args.no_llm)
        return

    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
