"""Plain scenario functions for the external vllmlx e2e runner."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from tests.e2e.harness import E2EError, ScenarioHarness


@dataclass(frozen=True)
class ScenarioDefinition:
    """Declarative scenario registration."""

    name: str
    func: Callable[[ScenarioHarness], dict]
    requires_cached_models: tuple[str, ...] = ()
    explicit_launchd: bool = False


def startup_serve(harness: ScenarioHarness) -> dict:
    config = harness.base_config()
    harness.write_config(config)
    serve = harness.start_process(["serve"], name="startup_serve")
    harness.wait_for_health(timeout=45.0)

    health = harness.request("GET", "/health")
    status = harness.request("GET", "/v1/status")
    if health.json() != {"status": "ok"}:
        raise E2EError("Serve health endpoint did not return ok")
    if status.json().get("status") != "not_loaded":
        raise E2EError("Expected unloaded /v1/status before first request")

    serve.terminate()

    preload = harness.base_config()
    preload.daemon.preload_default_model = True
    preload.daemon.pin_default_model = True
    preload.models.default = harness.primary_model
    harness.write_config(preload)
    serve = harness.start_process(["serve"], name="startup_serve_preload")
    harness.wait_for_health(timeout=90.0)
    status_after = harness.request("GET", "/v1/status").json()
    loaded = status_after.get("models") or []
    if harness.primary_model not in loaded:
        raise E2EError("Pinned preload did not load the default model at startup")

    return {
        "serve_pid": serve.pid,
        "status_before": status.json(),
        "status_after": status_after,
        "default_model": harness.primary_model,
    }


def startup_launchd(harness: ScenarioHarness) -> dict:
    harness.ensure_isolated_launchd()
    config = harness.base_config()
    config.models.default = harness.primary_model
    harness.write_config(config)

    start = harness.run_cli(["daemon", "start"], timeout=30.0)
    harness.wait_for_health(timeout=60.0)
    status = harness.run_cli(["daemon", "status"], timeout=15.0)
    api_status = harness.request("GET", "/v1/status").json()
    stop = harness.run_cli(["daemon", "stop"], timeout=30.0)
    plist_path = harness.launchd_plist_path()

    if not plist_path.exists():
        raise E2EError("Launchd plist was not created in the isolated directory")
    if "running" not in status.stdout.lower():
        raise E2EError("Daemon status did not report running under launchd")

    return {
        "start_stdout": start.stdout.strip(),
        "status_stdout": status.stdout.strip(),
        "stop_stdout": stop.stdout.strip(),
        "api_status": api_status,
        "plist_path": str(plist_path),
    }


def api_core(harness: ScenarioHarness) -> dict:
    config = harness.base_config()
    harness.write_config(config)
    serve = harness.start_process(["serve"], name="api_core")
    harness.wait_for_health(timeout=45.0)

    empty_status = harness.request("GET", "/v1/status").json()
    empty_models = harness.request("GET", "/v1/models").json()
    missing_model = harness.request(
        "POST",
        "/v1/chat/completions",
        json={"messages": [{"role": "user", "content": "hello"}]},
    )
    if missing_model.status_code != 503:
        raise E2EError("Expected 503 for chat request without model and no loaded backend")

    non_stream = harness.request(
        "POST",
        "/v1/chat/completions",
        json={
            "model": harness.primary_model,
            "messages": [{"role": "user", "content": "Say hello in one short sentence."}],
            "stream": False,
            "max_tokens": 32,
        },
    )
    if non_stream.status_code != 200:
        raise E2EError(f"Non-stream chat failed: {non_stream.text}")
    non_stream_payload = non_stream.json()
    response_text = harness.chat_text(non_stream_payload)
    if not response_text.strip():
        raise E2EError("Non-stream chat returned empty assistant content")

    loaded_status = harness.request("GET", "/v1/status").json()
    if harness.primary_model not in (loaded_status.get("models") or []):
        raise E2EError("Loaded model missing from /v1/status after chat request")

    streamed = harness.stream_chat(
        {
            "model": harness.primary_model,
            "messages": [{"role": "user", "content": "Count to three."}],
            "stream": True,
            "max_tokens": 16,
        }
    )
    if "data:" not in streamed or "[DONE]" not in streamed:
        raise E2EError("Streaming chat did not return SSE chunks and [DONE]")

    return {
        "serve_pid": serve.pid,
        "empty_status": empty_status,
        "empty_models": empty_models,
        "loaded_status": loaded_status,
        "response_preview": response_text[:120],
    }


def run_cli(harness: ScenarioHarness) -> dict:
    config = harness.base_config()
    harness.write_config(config)
    session = harness.start_pty(["run", harness.primary_model], name="run_cli")
    banner = session.read_until("vllmlx chat", "> ", timeout=60.0)
    if "vllmlx chat" not in banner:
        raise E2EError("REPL banner did not appear")

    session.send_line("Reply with one short greeting.")
    transcript = session.read_until("> ", timeout=300.0)
    if "Error:" in transcript:
        raise E2EError(f"Interactive run returned an error:\n{transcript}")

    session.send_line("/history")
    history = session.read_until("> ", timeout=15.0)
    if "Assistant:" not in history:
        raise E2EError("Interactive history did not include an assistant reply")

    session.send_line("/exit")
    goodbye = session.read_until("Goodbye!", timeout=15.0)
    if "Goodbye!" not in goodbye:
        raise E2EError("Interactive run did not exit cleanly")

    return {
        "session_pid": session.pid,
        "history_tail": history[-400:],
    }


def benchmark_smoke(harness: ScenarioHarness) -> dict:
    config = harness.base_config()
    harness.write_config(config)
    result = harness.run_cli(
        [
            "benchmark",
            harness.primary_model,
            "--json",
            "-n",
            "1",
            "-t",
            "16",
            "--warmup",
            "0",
        ],
        timeout=1800.0,
    )
    payload = result.stdout.strip()
    data = __import__("json").loads(payload)
    for key in ("model", "warm_start_time_s", "memory_peak", "total_iterations"):
        if key not in data:
            raise E2EError(f"Benchmark JSON missing required key: {key}")
    if data["model"] != harness.primary_model:
        raise E2EError("Benchmark JSON did not resolve to the canonical primary model")
    if data["warm_start_time_s"] < 0 or data["total_iterations"] < 0:
        raise E2EError("Benchmark JSON contained invalid negative metrics")
    return data


def downloads_tiny(harness: ScenarioHarness) -> dict:
    config = harness.base_config()
    harness.write_config(config)

    first = harness.run_cli(["pull", harness.download_model], timeout=1800.0)
    listing = harness.run_cli(["ls"], timeout=60.0)
    second = harness.run_cli(["pull", harness.download_model], timeout=300.0)
    removed = harness.run_cli(["rm", harness.download_model, "--force"], timeout=300.0)

    if harness.download_model.lower() not in listing.stdout.lower():
        raise E2EError("Downloaded tiny model was not listed by `vllmlx ls`")
    if "already downloaded" not in second.stdout.lower():
        raise E2EError("Cached re-pull did not report an existing download")
    if "removed" not in removed.stdout.lower():
        raise E2EError("Tiny model removal did not report success")

    return {
        "first_pull": first.stdout.strip(),
        "second_pull": second.stdout.strip(),
        "remove": removed.stdout.strip(),
    }


def lru_and_reuse(harness: ScenarioHarness) -> dict:
    config = harness.base_config()
    config.daemon.max_loaded_models = 2
    config.models.default = harness.primary_model
    harness.write_config(config)
    serve = harness.start_process(["serve"], name="lru_and_reuse")
    harness.wait_for_health(timeout=45.0)

    for model in (harness.primary_model, harness.secondary_model):
        response = harness.request(
            "POST",
            "/v1/chat/completions",
            json={
                "model": model,
                "messages": [{"role": "user", "content": "hello"}],
                "stream": False,
                "max_tokens": 8,
            },
        )
        if response.status_code != 200:
            raise E2EError(f"Failed to load model {model}: {response.text}")

    workers_before = {worker.model: worker for worker in harness.worker_snapshots()}
    primary_worker = workers_before.get(harness.primary_model)
    secondary_worker = workers_before.get(harness.secondary_model)
    if primary_worker is None or secondary_worker is None:
        raise E2EError("Expected both primary and secondary workers to be running")

    response = harness.request(
        "POST",
        "/v1/chat/completions",
        json={
            "model": harness.secondary_model,
            "messages": [{"role": "user", "content": "hello again"}],
            "stream": False,
            "max_tokens": 8,
        },
    )
    if response.status_code != 200:
        raise E2EError("Failed to reuse the secondary model worker")
    workers_after_reuse = {worker.model: worker for worker in harness.worker_snapshots()}
    if workers_after_reuse[harness.secondary_model].pid != secondary_worker.pid:
        raise E2EError("Expected the same worker PID when reusing a loaded model")

    if not harness.is_model_cached(harness.download_model):
        raise E2EError(
            f"The tertiary LRU model must be cached before this scenario: {harness.download_model}"
        )

    third = harness.request(
        "POST",
        "/v1/chat/completions",
        json={
            "model": harness.download_model,
            "messages": [{"role": "user", "content": "hello third"}],
            "stream": False,
            "max_tokens": 8,
        },
    )
    if third.status_code != 200:
        raise E2EError(f"Failed to load the tertiary model: {third.text}")

    status = harness.request("GET", "/v1/status").json()
    loaded_models = status.get("models") or []
    if harness.primary_model in loaded_models:
        raise E2EError("LRU eviction did not unload the oldest model")
    if loaded_models[:2] != [harness.download_model, harness.secondary_model]:
        raise E2EError("Loaded model recency order did not match expected LRU order")

    serve.terminate()

    pinned = harness.base_config()
    pinned.daemon.idle_timeout = 2
    pinned.daemon.pin_default_model = True
    pinned.models.default = harness.primary_model
    harness.write_config(pinned)
    serve = harness.start_process(["serve"], name="lru_and_reuse_pinned")
    harness.wait_for_health(timeout=45.0)
    time.sleep(3.5)
    pinned_status = harness.request("GET", "/v1/status").json()
    if harness.primary_model not in (pinned_status.get("models") or []):
        raise E2EError("Pinned default model was unloaded after idle timeout")

    return {
        "primary_worker_pid": primary_worker.pid,
        "secondary_worker_pid": secondary_worker.pid,
        "loaded_models_after_lru": loaded_models,
        "pinned_status": pinned_status,
    }


def knob_propagation(harness: ScenarioHarness) -> dict:
    mcp_config = harness.artifacts_dir / "mcp.json"
    mcp_config.write_text("{}", encoding="utf-8")

    config = harness.base_config()
    config.backend.continuous_batching = True
    config.backend.max_num_seqs = 17
    config.backend.max_num_batched_tokens = 4096
    config.backend.scheduler_policy = "priority"
    config.backend.prefill_step_size = 1024
    config.backend.enable_prefix_cache = False
    config.backend.prefix_cache_size = 77
    config.backend.cache_memory_percent = 0.15
    config.backend.use_paged_cache = True
    config.backend.paged_cache_block_size = 32
    config.backend.max_cache_blocks = 123
    config.backend.chunked_prefill_tokens = 256
    config.backend.mid_prefill_save_interval = 512
    config.backend.api_key = "e2e-test-key"
    config.backend.rate_limit = 11
    config.backend.timeout = 123.0
    config.backend.reasoning_parser = "qwen3"
    config.backend.default_temperature = 0.2
    config.backend.default_top_p = 0.85
    config.backend.embedding_model = harness.secondary_model
    config.backend.mcp_config = str(mcp_config)
    harness.write_config(config)

    harness.start_process(["serve"], name="knob_propagation")
    harness.wait_for_health(timeout=45.0)
    response = harness.request(
        "POST",
        "/v1/chat/completions",
        json={
            "model": harness.primary_model,
            "messages": [{"role": "user", "content": "hello"}],
            "stream": False,
            "max_tokens": 8,
        },
    )
    if response.status_code != 200:
        raise E2EError(f"Failed to start backend with knob config: {response.text}")

    workers = harness.worker_snapshots()
    if not workers:
        raise E2EError("No backend worker process found for knob propagation")
    worker = workers[0]
    argv = " ".join(worker.argv)

    required_pairs = {
        "--continuous-batching": None,
        "--max-num-seqs": "17",
        "--max-num-batched-tokens": "4096",
        "--scheduler-policy": "priority",
        "--prefill-step-size": "1024",
        "--disable-prefix-cache": None,
        "--prefix-cache-size": "77",
        "--cache-memory-percent": "0.15",
        "--use-paged-cache": None,
        "--paged-cache-block-size": "32",
        "--max-cache-blocks": "123",
        "--chunked-prefill-tokens": "256",
        "--mid-prefill-save-interval": "512",
        "--api-key": "e2e-test-key",
        "--rate-limit": "11",
        "--timeout": "123.0",
        "--reasoning-parser": "qwen3",
        "--default-temperature": "0.2",
        "--default-top-p": "0.85",
        "--embedding-model": harness.secondary_model,
    }
    for flag, value in required_pairs.items():
        if flag not in worker.argv:
            raise E2EError(f"Missing propagated backend flag: {flag}\nargv={argv}")
        if value is None:
            continue
        index = worker.argv.index(flag)
        if index + 1 >= len(worker.argv) or worker.argv[index + 1] != value:
            raise E2EError(f"Unexpected value for {flag}: {worker.argv}")

    if worker.env.get("VLLM_MLX_MCP_CONFIG") != str(mcp_config):
        raise E2EError("Backend worker env did not include VLLM_MLX_MCP_CONFIG")

    return {
        "worker_pid": worker.pid,
        "worker_model": worker.model,
        "worker_port": worker.port,
        "argv": worker.argv,
    }


SCENARIOS: dict[str, ScenarioDefinition] = {
    "startup_serve": ScenarioDefinition(
        name="startup_serve",
        func=startup_serve,
        requires_cached_models=("mlx-community/Llama-3.2-1B-Instruct-4bit",),
    ),
    "startup_launchd": ScenarioDefinition(
        name="startup_launchd",
        func=startup_launchd,
        explicit_launchd=True,
    ),
    "api_core": ScenarioDefinition(
        name="api_core",
        func=api_core,
        requires_cached_models=("mlx-community/Llama-3.2-1B-Instruct-4bit",),
    ),
    "run_cli": ScenarioDefinition(
        name="run_cli",
        func=run_cli,
        requires_cached_models=("mlx-community/Llama-3.2-1B-Instruct-4bit",),
    ),
    "benchmark_smoke": ScenarioDefinition(
        name="benchmark_smoke",
        func=benchmark_smoke,
        requires_cached_models=("mlx-community/Llama-3.2-1B-Instruct-4bit",),
    ),
    "downloads_tiny": ScenarioDefinition(
        name="downloads_tiny",
        func=downloads_tiny,
    ),
    "lru_and_reuse": ScenarioDefinition(
        name="lru_and_reuse",
        func=lru_and_reuse,
        requires_cached_models=(
            "mlx-community/Llama-3.2-1B-Instruct-4bit",
            "mlx-community/TinyLlama-1.1B-Chat-v1.0-4bit",
        ),
    ),
    "knob_propagation": ScenarioDefinition(
        name="knob_propagation",
        func=knob_propagation,
        requires_cached_models=("mlx-community/Llama-3.2-1B-Instruct-4bit",),
    ),
}

SMOKE_SCENARIOS = ["startup_serve", "api_core", "run_cli", "benchmark_smoke"]
FULL_SCENARIOS = [
    "downloads_tiny",
    "startup_serve",
    "api_core",
    "run_cli",
    "benchmark_smoke",
    "lru_and_reuse",
    "knob_propagation",
]
