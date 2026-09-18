#!/usr/bin/env python3
"""Signalpost Agent CLI.

Examples:
  python main.py --org 923609016
  python main.py --bulk --count 1000
  python main.py --bulk --count 1000 --org-list company_numbers.txt
  python main.py --bulk --count 1000 --llm
  python main.py --update
"""
import argparse, json, sys
from src.agent import process_one, process_bulk, process_update
from src.budget_guard import BudgetGuard

def main():
    parser=argparse.ArgumentParser(description="Signalpost company research agent")
    parser.add_argument("--org",help="Norwegian organisation number")
    parser.add_argument("--bulk",action="store_true",help="Build a bulk profile dataset")
    parser.add_argument("--update",action="store_true",help="Refresh saved profiles")
    parser.add_argument("--count",type=int,default=1000,help="Number of companies in bulk mode")
    parser.add_argument("--org-list",help="Optional newline-delimited organisation-number file")
    parser.add_argument("--llm",action="store_true",help="Use Gemini summaries when request budget allows")
    parser.add_argument("--no-llm",action="store_true",help="Force deterministic local summaries")
    args=parser.parse_args()

    if args.org:
        guard=BudgetGuard()
        p=process_one(args.org,guard,use_llm=args.llm and not args.no_llm)
        print(json.dumps(p.to_dict(),ensure_ascii=False,indent=2)); return
    if args.update:
        process_update(use_llm=args.llm and not args.no_llm); return
    if args.bulk:
        process_bulk(target_count=args.count,use_llm=args.llm and not args.no_llm,
                     org_list_path=args.org_list); return
    parser.print_help(); sys.exit(1)

if __name__=="__main__":
    main()
