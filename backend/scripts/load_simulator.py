import argparse
import hashlib
import os
import threading
import time


def _gil_free_worker(stop_event: threading.Event) -> None:
    """Run C-level PBKDF2 hashing (releases Python GIL) to load a CPU core under this single PID."""
    payload = b"sentinelai-cpu-benchmark-payload"
    salt = b"sentinelai-salt"
    while not stop_event.is_set():
        hashlib.pbkdf2_hmac("sha256", payload, salt, 150_000)


def burn_cpu(duration: int, workers: int) -> None:
    print(
        f"[load_simulator] PID={os.getpid()} | Burning {workers} CPU core(s) under this single PID for {duration}s..."
    )
    stop_event = threading.Event()
    threads = [
        threading.Thread(target=_gil_free_worker, args=(stop_event,), daemon=True)
        for _ in range(workers)
    ]
    for t in threads:
        t.start()

    try:
        time.sleep(duration)
    finally:
        stop_event.set()
        for t in threads:
            t.join(timeout=1.0)
    print("[load_simulator] CPU load finished cleanly.")


def allocate_memory(megabytes: int, duration: int) -> None:
    print(
        f"[load_simulator] PID={os.getpid()} | Allocating ~{megabytes} MB RAM for {duration}s..."
    )
    chunks = [bytearray(1024 * 1024) for _ in range(megabytes)]
    for chunk in chunks:
        chunk[0] = 1
    time.sleep(duration)
    chunks.clear()
    print("[load_simulator] Memory released cleanly.")


def main() -> None:
    default_workers = max(2, (os.cpu_count() or 4) // 2)
    parser = argparse.ArgumentParser(description="Safe resource load simulator for SentinelAI demos.")
    parser.add_argument("--mode", choices=["cpu", "memory"], required=True)
    parser.add_argument("--duration", type=int, default=45, help="Duration in seconds (default: 45)")
    parser.add_argument(
        "--workers",
        type=int,
        default=default_workers,
        help=f"Number of CPU cores to load under this PID (default: {default_workers})",
    )
    parser.add_argument("--mb", type=int, default=256, help="Megabytes to allocate in memory mode")
    args = parser.parse_args()

    if args.mode == "cpu":
        burn_cpu(args.duration, args.workers)
    else:
        allocate_memory(args.mb, args.duration)


if __name__ == "__main__":
    main()