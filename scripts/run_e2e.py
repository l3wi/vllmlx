"""External runner for real-model vllmlx parity scenarios."""

from __future__ import annotations

# ruff: noqa: E402
import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.e2e.harness import ScenarioHarness, ScenarioResult
from tests.e2e.scenarios import FULL_SCENARIOS, SCENARIOS, SMOKE_SCENARIOS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run real-model vllmlx e2e parity scenarios.")
    parser.add_argument(
        "--mode",
        choices=["smoke", "full"],
        default="smoke",
        help="Scenario set to run (default: smoke).",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Run only the named scenario(s). Can be passed multiple times.",
    )
    parser.add_argument(
        "--allow-launchd",
        action="store_true",
        help="Enable the explicit startup_launchd scenario.",
    )
    parser.add_argument(
        "--artifacts-dir",
        default=str(REPO_ROOT / ".artifacts" / "e2e"),
        help="Directory for logs, PTY transcripts, and JSON reports.",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="Optional explicit path for the JSON report. Defaults under artifacts dir.",
    )
    parser.add_argument(
        "--model",
        default="mlx-community/Llama-3.2-1B-Instruct-4bit",
        help="Primary cached model for core API, run, and benchmark scenarios.",
    )
    parser.add_argument(
        "--secondary-model",
        default="mlx-community/TinyLlama-1.1B-Chat-v1.0-4bit",
        help="Secondary cached model used for live model-swap/LRU scenarios.",
    )
    parser.add_argument(
        "--download-model",
        default="mlx-community/AMD-Llama-135m-4bit",
        help="Tiny model used for download-only coverage.",
    )
    return parser.parse_args()


def resolve_scenarios(args: argparse.Namespace) -> list[str]:
    if args.scenario:
        names = args.scenario
    elif args.mode == "smoke":
        names = list(SMOKE_SCENARIOS)
    else:
        names = list(FULL_SCENARIOS)

    if args.allow_launchd and "startup_launchd" not in names:
        names.append("startup_launchd")
    return names


def main() -> int:
    args = parse_args()
    selected = resolve_scenarios(args)
    unknown = [name for name in selected if name not in SCENARIOS]
    if unknown:
        print(f"Unknown scenario(s): {', '.join(unknown)}", file=sys.stderr)
        return 2

    started = time.monotonic()
    artifacts_dir = Path(args.artifacts_dir).resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    report_path = (
        Path(args.json_report).resolve() if args.json_report else artifacts_dir / "report.json"
    )

    results: list[ScenarioResult] = []
    failures = 0

    print(f"Running {len(selected)} scenario(s) in {args.mode} mode")
    print(f"Artifacts: {artifacts_dir}")

    for name in selected:
        definition = SCENARIOS[name]
        if definition.explicit_launchd and not args.allow_launchd:
            results.append(
                ScenarioResult(
                    name=name,
                    status="skipped",
                    duration_s=0.0,
                    details={"reason": "launchd scenario requires --allow-launchd"},
                )
            )
            print(f"[skip] {name}: requires --allow-launchd")
            continue

        harness = ScenarioHarness(
            repo_root=REPO_ROOT,
            artifacts_root=artifacts_dir,
            name=name,
            primary_model=args.model,
            secondary_model=args.secondary_model,
            download_model=args.download_model,
            allow_launchd=args.allow_launchd,
        )
        scenario_started = time.monotonic()
        print(f"[run ] {name}")

        try:
            if definition.requires_cached_models:
                required = []
                for model in definition.requires_cached_models:
                    if model == "mlx-community/Llama-3.2-1B-Instruct-4bit":
                        required.append(args.model)
                    elif model == "mlx-community/TinyLlama-1.1B-Chat-v1.0-4bit":
                        required.append(args.secondary_model)
                    else:
                        required.append(model)
                harness.require_cached_models(required)

            details = definition.func(harness)
            result = ScenarioResult(
                name=name,
                status="passed",
                duration_s=time.monotonic() - scenario_started,
                details=details,
                artifacts={
                    "artifacts_dir": str(harness.artifacts_dir),
                    "state_dir": str(harness.state_dir),
                },
            )
            results.append(result)
            print(f"[pass] {name} ({result.duration_s:.1f}s)")
        except KeyboardInterrupt:
            print(f"[fail] {name}: interrupted", file=sys.stderr)
            failures += 1
            results.append(
                ScenarioResult(
                    name=name,
                    status="failed",
                    duration_s=time.monotonic() - scenario_started,
                    error="interrupted",
                    artifacts={"artifacts_dir": str(harness.artifacts_dir)},
                )
            )
            break
        except Exception as exc:
            failures += 1
            results.append(
                ScenarioResult(
                    name=name,
                    status="failed",
                    duration_s=time.monotonic() - scenario_started,
                    error=str(exc),
                    artifacts={"artifacts_dir": str(harness.artifacts_dir)},
                )
            )
            print(f"[fail] {name}: {exc}", file=sys.stderr)
        finally:
            harness.cleanup()

    report: dict[str, Any] = {
        "mode": args.mode,
        "selected_scenarios": selected,
        "allow_launchd": args.allow_launchd,
        "models": {
            "primary": args.model,
            "secondary": args.secondary_model,
            "download": args.download_model,
        },
        "duration_s": time.monotonic() - started,
        "failures": failures,
        "results": [result.__dict__ for result in results],
    }
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"JSON report: {report_path}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
