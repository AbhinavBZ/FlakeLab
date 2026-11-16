
import json
import subprocess
import sys
import time

from collections import defaultdict
from pathlib import Path

import yaml


def load_config(config_path):
    """Load and validate the experiment configuration."""

    config_path = Path(config_path).resolve()

    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")

    with config_path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError("Invalid YAML configuration.")

    return config, config_path.parent.parent


def run_seed(project_root, test_path, seed, timeout, results_dir):
    """Execute pytest using one random seed."""

    report_path = results_dir / f"seed_{seed}.json"
    log_path = results_dir / f"seed_{seed}.log"

    command = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        "-v",
        "--random-order",
        f"--random-order-seed={seed}",
        "--json-report",
        f"--json-report-file={report_path}",
    ]

    start_time = time.perf_counter()

    try:
        process = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

        duration = round(time.perf_counter() - start_time, 4)

        log_path.write_text(
            process.stdout + "\n" + process.stderr,
            encoding="utf-8",
        )

        if report_path.exists():
            report = json.loads(
                report_path.read_text(encoding="utf-8")
            )
        else:
            report = {}

        test_results = {}

        for test in report.get("tests", []):
            nodeid = test.get("nodeid")
            outcome = test.get("outcome")

            if nodeid and outcome:
                test_results[nodeid] = outcome

        return {
            "seed": seed,
            "return_code": process.returncode,
            "duration_seconds": duration,
            "tests": test_results,
            "timed_out": False,
            "log_file": str(log_path),
        }

    except subprocess.TimeoutExpired:
        duration = round(time.perf_counter() - start_time, 4)

        log_path.write_text(
            "Experiment timed out.",
            encoding="utf-8",
        )

        return {
            "seed": seed,
            "return_code": None,
            "duration_seconds": duration,
            "tests": {},
            "timed_out": True,
            "log_file": str(log_path),
        }


def analyze_results(runs):
    """Identify tests with inconsistent pass/fail outcomes."""

    outcomes = defaultdict(set)

    for run in runs:
        for test_name, result in run["tests"].items():
            outcomes[test_name].add(result)

    inconsistent_tests = []

    for test_name, test_outcomes in outcomes.items():

        has_pass = "passed" in test_outcomes
        has_failure = bool(
            test_outcomes.intersection({"failed", "error"})
        )

        if has_pass and has_failure:
            inconsistent_tests.append({
                "test": test_name,
                "outcomes": sorted(test_outcomes),
                "classification": "inconsistent",
            })

    return inconsistent_tests


def execute_experiment(config_path):
    """Run all configured experiments and generate a JSON report."""

    config, project_root = load_config(config_path)

    project = config.get("project", {})
    execution = config.get("execution", {})
    scenario = config.get("scenarios", {}).get(
        "order_variation", {}
    )

    if not scenario.get("enabled", False):
        raise ValueError("Order variation scenario is disabled.")

    test_path = project.get("test_path", "tests")
    repetitions = execution.get("repetitions", 10)
    timeout = execution.get("timeout_seconds", 120)

    seeds = scenario.get("seeds", [])

    if not isinstance(seeds, list) or not seeds:
        raise ValueError("At least one random seed is required.")

    results_dir = project_root / "results"
    raw_dir = results_dir / "raw"

    raw_dir.mkdir(parents=True, exist_ok=True)

    runs = []

    print("\nStarting FlakeLab experiment...\n")

    for index, seed in enumerate(seeds[:repetitions], start=1):

        print(f"[{index}] Executing with seed {seed}")

        result = run_seed(
            project_root,
            test_path,
            seed,
            timeout,
            raw_dir,
        )

        runs.append(result)

        print(
            f"    Return code: {result['return_code']}"
            f" | Duration: {result['duration_seconds']}s"
        )

    inconsistent_tests = analyze_results(runs)

    summary = {
        "project": project.get("name", "FlakeLab"),
        "scenario": "order_variation",
        "total_runs": len(runs),
        "successful_runs": sum(
            1 for run in runs if run["return_code"] == 0
        ),
        "failed_runs": sum(
            1 for run in runs if run["return_code"] not in (0, None)
        ),
        "timed_out_runs": sum(
            1 for run in runs if run["timed_out"]
        ),
        "inconsistent_tests": inconsistent_tests,
        "runs": runs,
    }

    report_path = results_dir / "experiment.json"

    report_path.write_text(
        json.dumps(summary, indent=4),
        encoding="utf-8",
    )

    print("\nExperiment completed.")
    print(f"Inconsistent tests: {len(inconsistent_tests)}")
    print(f"Report saved: {report_path}")


if __name__ == "__main__":
    execute_experiment("configs/experiment.yaml")
