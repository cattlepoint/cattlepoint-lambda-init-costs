#!/usr/bin/env python3
"""
lambda_init_costs.py
Estimate per‑function cold‑start (Init Duration) costs for all ZIP‑package Lambda
functions over a user‑defined look‑back window (default 30 days).

Improvements over the original script
-------------------------------------
* **Region handling** – use --region CLI flag, $AWS_REGION, or the active AWS profile; removed undefined `REGION` global.
* **CLI parameters** – configurable region, days back, and output file.
* **Robust cost math** – uses `decimal.Decimal` for currency‑safe rounding.
* **Safety checks** – skips functions that raise API errors or have zero cold starts.
* **Sorted output** – CSV ordered by highest monthly cost so the costliest functions surface first.
* **Code hygiene** – smaller helpers, `argparse`, type‑safe constants, and early exits.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import os
import sys
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterator

import boto3
from botocore.exceptions import ClientError

DEFAULT_DAYS_BACK = 30
PRICE_PER_GB_SECOND = Decimal("0.0000166667")  # 2025‑07 AWS Lambda pricing

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _info(msg: str) -> None:
    """Emit an informational message immediately."""
    print(f"[INFO] {msg}", flush=True)

def parse_args() -> argparse.Namespace:  # noqa: D401
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Estimate the monthly cost of cold‑start init duration across all "
            "ZIP‑based Lambda functions in an AWS account."
        )
    )
    parser.add_argument(
        "--region",
        help="AWS region (falls back to $AWS_REGION or the current AWS profile).",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS_BACK,
        help=f"How many days back to scan CloudWatch Logs (default {DEFAULT_DAYS_BACK}).",
    )
    parser.add_argument(
        "--outfile",
        default="lambda_init_costs_filtered.csv",
        help="Destination CSV file (default: lambda_init_costs_filtered.csv).",
    )
    return parser.parse_args()


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def main() -> None:  # pragma: no cover
    args = parse_args()

    region = args.region or os.getenv("AWS_REGION") or boto3.Session().region_name
    if not region:
        raise SystemExit(
            "AWS region not set\n"
            "Supply --region, set $AWS_REGION, or configure a default region in the AWS CLI."
        )

    _info(
        f"Scanning region {region} for the past {args.days} day(s). Output → {args.outfile}"
    )

    logs = boto3.client("logs", region_name=region)
    lam = boto3.client("lambda", region_name=region)

    end_ms = int(dt.datetime.now(tz=dt.timezone.utc).timestamp() * 1000)
    start_ms = int(
        (dt.datetime.now(tz=dt.timezone.utc) - dt.timedelta(days=args.days)).timestamp() * 1000
    )

    def log_groups() -> Iterator[str]:
        _info("Listing CloudWatch log groups…")
        paginator = logs.get_paginator("describe_log_groups")
        for page in paginator.paginate(logGroupNamePrefix="/aws/lambda/"):
            yield from (g["logGroupName"] for g in page["logGroups"])

    rows: list[list[str | int | float]] = []
    grand_total = Decimal("0")

    for lg in log_groups():
        fn_name = lg.rsplit("/", 1)[-1]
        _info(f"Analyzing {fn_name}")
        try:
            cfg = lam.get_function_configuration(FunctionName=fn_name)
        except ClientError as exc:
            _info(f"Skipping {fn_name}: {exc.response['Error']['Code']}")
            continue

        if cfg.get("PackageType") != "Zip":
            _info(f"Skipping {fn_name}: not ZIP package")
            continue  # skip container‑image Lambdas
        if cfg.get("Runtime", "").startswith("provided"):
            _info(f"Skipping {fn_name}: custom runtime")
            continue  # skip custom runtimes

        # Query only the message field for speed
        messages: list[str] = []
        paginator = logs.get_paginator("filter_log_events")
        for page in paginator.paginate(
            logGroupName=lg,
            filterPattern='"Init Duration"',  # exact phrase match
            startTime=start_ms,
            endTime=end_ms,
            PaginationConfig={"MaxItems": 100_000, "PageSize": 1_000},
        ):
            messages.extend(evt["message"] for evt in page["events"])

        cold_starts = len(messages)
        if cold_starts == 0:
            _info(f"{fn_name}: 0 cold starts – skipping")
            continue

        _info(f"{fn_name}: {cold_starts} cold starts found")

        init_ms = [float(msg.split("Init Duration: ")[1].split()[0]) for msg in messages]
        avg_ms = average(init_ms)

        mem_mb = cfg.get("MemorySize", 128)
        init_sec = avg_ms / 1_000.0
        cost = (
            Decimal(str(init_sec))
            * Decimal(mem_mb)
            / Decimal(1_024)
            * PRICE_PER_GB_SECOND
            * cold_starts
        ).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)

        grand_total += cost
        rows.append([fn_name, cold_starts, f"{avg_ms:.2f}", mem_mb, f"{cost:.6f}"])

    rows.sort(key=lambda r: Decimal(r[4]), reverse=True)

    header = [
        "Function Name",
        "Cold Start Count",
        "Avg Init Duration (ms)",
        "Memory (MB)",
        "Monthly Init Cost (USD)",
    ]

    _info("Writing CSV output…")
    with open(args.outfile, "w", newline="") as fp:
        writer = csv.writer(fp)
        writer.writerow(header)
        writer.writerows(rows)
        writer.writerow(["", "", "", "Total Monthly INIT Cost (USD)", f"{grand_total:.6f}"])

    _info(f"Report saved to {args.outfile}. Total cost USD {grand_total:.6f}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        _info("Interrupted by user – exiting")
        sys.exit(130)
