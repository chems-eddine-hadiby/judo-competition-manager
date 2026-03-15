# -*- coding: utf-8 -*-
"""
github_test.py — quick connectivity test for GitHub sync
Run: python github_test.py
Requires: env var GITHUB_TOKEN
"""
import os
import sys
import github_sync as gsync

def main():
    token = os.environ.get("GITHUB_TOKEN", "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").strip()
    if not token:
        print("Missing GITHUB_TOKEN environment variable.")
        return 2
    try:
        comps = gsync.list_competitions(token)
    except Exception as e:
        print(f"ERROR: {e}")
        return 1
    print("OK. Competitions:")
    for name in comps:
        print(f"- {name}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
