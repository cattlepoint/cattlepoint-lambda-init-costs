# cattlepoint-lambda-init-costs

Estimate the monthly **cold‑start (Init Duration)** cost for every ZIP‑package AWS Lambda function in an account.

---

### Vibe coded project; use at your own risk.

---

## Key capabilities

* **Region aware** – `--region` flag, `$AWS_REGION`, or current AWS profile.
* **Adjustable window** – `--days N` scans CloudWatch Logs going back *N* days (default 30).
* **Safe currency math** – `decimal.Decimal` rounds to micro‑dollar precision.
* **Skips noise** – ignores container‑image Lambdas, custom runtimes, zero‑hit functions, and API errors.
* **Actionable output** – CSV ordered by **highest monthly cost first** so you can prioritize optimization.

## Requirements

* Python 3.9+
* AWS credentials with permission to read CloudWatch Logs and Lambda configurations
* [boto3](https://pypi.org/project/boto3/) (installed below)

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -U boto3
git clone https://github.com/cattlepoint/cattlepoint-lambda-init-costs.git
cd cattlepoint-lambda-init-costs
```

## CLI

```bash
python cattlepoint-lambda-init-costs.py \
  --region us-east-1 \        # optional
  --days 14 \                 # optional (default 30)
  --outfile init_costs.csv    # optional
```

### Parameters

| Flag        | Default                          | Description                                                         |
| ----------- | -------------------------------- | ------------------------------------------------------------------- |
| `--region`  | env/CLI                          | AWS Region. Falls back to `$AWS_REGION` or your active AWS profile. |
| `--days`    | **30**                           | Look‑back window in days for CloudWatch Logs.                       |
| `--outfile` | `lambda_init_costs_filtered.csv` | CSV report destination.                                             |

## Example run

```text
% python cattlepoint-lambda-init-costs.py --days 1
[INFO] Scanning region us-east-1 for the past 1 day(s). Output → lambda_init_costs_filtered.csv
[INFO] Listing CloudWatch log groups…
[INFO] Analyzing FunctionA-Primary
[INFO] FunctionA-Primary: 12 cold starts found
[INFO] Analyzing FunctionA-Secondary
[INFO] FunctionA-Secondary: 0 cold starts – skipping
[INFO] Analyzing FunctionB-Primary
[INFO] FunctionB-Primary: 13 cold starts found
[INFO] Analyzing FunctionB-Secondary
[INFO] FunctionB-Secondary: 0 cold starts – skipping
[INFO] Analyzing FunctionC-Activation
[INFO] FunctionC-Activation: 0 cold starts – skipping
[INFO] Analyzing FunctionD-Seeder
[INFO] Skipping FunctionD-Seeder: ResourceNotFoundException
[INFO] Analyzing FunctionE-Authorizer
[INFO] Skipping FunctionE-Authorizer: ResourceNotFoundException
[INFO] Analyzing FunctionF-Helper
[INFO] Skipping FunctionF-Helper: ResourceNotFoundException
[INFO] Analyzing FunctionG-ConfigWriter
[INFO] Skipping FunctionG-ConfigWriter: ResourceNotFoundException
[INFO] Analyzing FunctionH-CheckGenerator
[INFO] Skipping FunctionH-CheckGenerator: ResourceNotFoundException
[INFO] Analyzing FunctionH-OverdueScanner
[INFO] FunctionH-OverdueScanner: 12 cold starts found
[INFO] Analyzing FunctionI-CheckGenerator
[INFO] Skipping FunctionI-CheckGenerator: ResourceNotFoundException
[INFO] Analyzing FunctionI-OverdueScanner
[INFO] Skipping FunctionI-OverdueScanner: ResourceNotFoundException
[INFO] Writing CSV output…
[INFO] Report saved to lambda_init_costs_filtered.csv. Total cost USD 0.000018
```

## How it works

1. **Discover log groups** – enumerates `/aws/lambda/*` CloudWatch Log Groups.
2. **Fetch init events** – filters logs for `"Init Duration"` between *start* and *end* epoch milliseconds.
3. **Calculate cost** for each function:

```
cost = (avg_init_ms / 1000)   # seconds
        * (memory_mb / 1024)  # GB
        * price_per_GB_second # $0.0000166667 (July 2025 us‑east‑1)
        * cold_start_count
```

4. **Aggregate & sort** by cost, write results + totals to CSV.

## Pricing reference

As of **July 1 2025**, Lambda GB‑second price in `us‑east‑1` is **\$0.0000166667**. Adjust `PRICE_PER_GB_SECOND` in the script if AWS updates pricing.

## License

[MIT](LICENSE)
