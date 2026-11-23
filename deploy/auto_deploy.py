#!/usr/bin/env python3
"""Deploy the current main commit after its GitHub Actions tests pass."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def git(checkout, *args):
    return subprocess.check_output(["git", *args], cwd=checkout, text=True).strip()


def tests_passed(repository, revision):
    query = urlencode(dict(branch="main", event="push", head_sha=revision, per_page=1))
    request = Request(
        f"https://api.github.com/repos/{repository}/actions/workflows/tests.yml/runs?{query}",
        headers={"Accept": "application/vnd.github+json"},
    )
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        request.add_header("Authorization", f"Bearer {token}")
    with urlopen(request, timeout=30) as response:
        runs = json.load(response)["workflow_runs"]
    return bool(runs and runs[0]["head_sha"] == revision and runs[0]["conclusion"] == "success")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="Dedicated Git checkout for deployment")
    parser.add_argument("state", type=Path, help="File recording the last applied commit")
    parser.add_argument("--baseline", action="store_true", help="Record current main without deploying")
    args = parser.parse_args()
    origin = git(args.checkout, "remote", "get-url", "origin")
    match = re.fullmatch(r"https://github\.com/([\w.-]+/[\w.-]+?)(?:\.git)?", origin)
    if not match:
        parser.error("origin must be a GitHub HTTPS URL without credentials")

    git(args.checkout, "fetch", "--no-tags", "origin", "refs/heads/main")
    revision = git(args.checkout, "rev-parse", "FETCH_HEAD")
    if args.state.exists() and args.state.read_text().strip() == revision:
        return
    if args.baseline and args.state.exists():
        parser.error("a baseline already exists")
    if not args.baseline:
        if not args.state.exists():
            parser.error("record the initial baseline before enabling automatic deployment")
        if not tests_passed(match[1], revision):
            print(f"Waiting for successful main tests for {revision}", flush=True)
            return
        git(args.checkout, "checkout", "--detach", revision)
        environment = dict(os.environ, RELEASE=f"git-{revision}")
        subprocess.run(["bash", "deploy/deploy.sh"], cwd=args.checkout, env=environment, check=True)

    pending = args.state.with_suffix(".tmp")
    pending.write_text(revision + "\n")
    pending.replace(args.state)
    print(f"{'Baseline' if args.baseline else 'Deployed'}: {revision}", flush=True)


if __name__ == "__main__":
    main()
