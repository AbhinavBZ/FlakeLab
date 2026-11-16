
import json
import argparse

from pathlib import Path
from .replay import replay_seed


def run_reliability_analysis(seed, attempts):
    """Replay a failing seed multiple times and measure reliability."""

    project_root = Path(__file__).resolve().parents[2]

    results_dir = project_root / "results" / "replays"
    results_dir.mkdir(parents=True, exist_ok=True)

    results = []

    print(f"\nStarting reliability analysis for seed {seed}")
    print(f"Total replay attempts: {attempts}\n")

    for attempt in range(1, attempts + 1):
        print(f"Replay attempt {attempt}/{attempts}")

        result = replay_seed(seed, attempt=attempt)

        reproduced = result["failure_reproduced"]

        results.append({
            "attempt": attempt,
            "failure_reproduced": reproduced,
            "reproduced_tests": result.get(
                "reproduced_tests", []
            ),
            "duration_seconds": result["duration_seconds"],
        })

        print(f"Failure reproduced: {reproduced}\n")

    reproduced_count = sum(
        1 for result in results
        if result["failure_reproduced"]
    )

    reproduction_rate = round(
        (reproduced_count / attempts) * 100, 2
    )

    summary = {
        "seed": seed,
        "total_attempts": attempts,
        "successful_reproductions": reproduced_count,
        "unsuccessful_reproductions": attempts - reproduced_count,
        "reproduction_rate_percent": reproduction_rate,
        "attempts": results,
    }

    report_path = (
        results_dir / f"reliability_seed_{seed}.json"
    )

    report_path.write_text(
        json.dumps(summary, indent=4),
        encoding="utf-8",
    )

    print("\nReliability analysis completed.")
    print(f"Successful reproductions: {reproduced_count}/{attempts}")
    print(f"Reproduction rate: {reproduction_rate}%")
    print(f"Report saved: {report_path}")

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="FlakeLab multi-replay reliability analysis"
    )

    parser.add_argument("--seed", type=int, default=4)
    parser.add_argument("--attempts", type=int, default=5)

    args = parser.parse_args()

    if args.attempts < 1:
        parser.error("--attempts must be at least 1")

    run_reliability_analysis(args.seed, args.attempts)
