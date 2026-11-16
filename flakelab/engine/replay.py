
import json
import subprocess
import sys
import time

from pathlib import Path


def load_experiment():
    """Load the previous experiment without modifying it."""
    project_root = Path(__file__).resolve().parents[2]
    report_path = project_root / "results" / "experiment.json"

    if not report_path.exists():
        raise FileNotFoundError(
            "No previous experiment found. Run the executor first."
        )

    with report_path.open("r", encoding="utf-8") as file:
        return json.load(file), project_root


def replay_seed(seed):
    """Replay a specific random seed from the previous experiment."""
    experiment, project_root = load_experiment()

    original_run = next(
        (run for run in experiment["runs"] if run["seed"] == seed),
        None
    )

    if original_run is None:
        raise ValueError(f"Seed {seed} was not found.")

    config_path = project_root / "configs" / "experiment.yaml"

    import yaml

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    test_path = config.get("project", {}).get("test_path", "tests")

    replay_dir = project_root / "results" / "replays"
    replay_dir.mkdir(parents=True, exist_ok=True)

    report_path = replay_dir / f"replay_seed_{seed}.json"
    log_path = replay_dir / f"replay_seed_{seed}.log"

    command = [
        sys.executable,
        "-m", "pytest",
        test_path,
        "-v",
        "--random-order",
        f"--random-order-seed={seed}",
        "--json-report",
        f"--json-report-file={report_path}",
    ]

    print(f"\nReplaying experiment with seed: {seed}")
    start = time.perf_counter()

    process = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=config.get("execution", {}).get(
            "timeout_seconds", 60
        ),
        check=False,
    )

    duration = round(time.perf_counter() - start, 4)

    log_path.write_text(
        process.stdout + "\n" + process.stderr,
        encoding="utf-8"
    )

    if report_path.exists():
        replay_report = json.loads(
            report_path.read_text(encoding="utf-8")
        )
    else:
        replay_report = {}

    replay_outcomes = {
        test["nodeid"]: test["outcome"]
        for test in replay_report.get("tests", [])
        if test.get("nodeid") and test.get("outcome")
    }

    original_outcomes = original_run["tests"]

    comparisons = []

    for test_name, original_result in original_outcomes.items():
        replay_result = replay_outcomes.get(test_name, "not_found")

        comparisons.append({
            "test": test_name,
            "original": original_result,
            "replay": replay_result,
            "same_outcome": original_result == replay_result,
        })

    replay_result = {
        "seed": seed,
        "duration_seconds": duration,
        "original_return_code": original_run["return_code"],
        "replay_return_code": process.returncode,
        "comparisons": comparisons,
        "failure_reproduced": (
            original_run["return_code"] != 0
            and process.returncode != 0
        ),
        "log_file": str(log_path),
    }

    output_path = replay_dir / f"comparison_seed_{seed}.json"

    output_path.write_text(
        json.dumps(replay_result, indent=4),
        encoding="utf-8"
    )

    print("\nReplay completed.")
    print(f"Original exit code: {original_run['return_code']}")
    print(f"Replay exit code: {process.returncode}")
    print(
        "Failure reproduced:",
        replay_result["failure_reproduced"]
    )
    print(f"Comparison saved: {output_path}")

    return replay_result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Replay a previous FlakeLab experiment."
    )
    parser.add_argument(
        "--seed",
        type=int,
        required=True,
        help="Random seed to replay."
    )

    args = parser.parse_args()
    replay_seed(args.seed)
