import argparse
import os
import time


def burn_cpu(duration: int) -> None:
    print(f"[load_simulator] PID={os.getpid()} | Burning 1 CPU core for {duration}s...")
    end_time = time.time() + duration
    counter = 0
    while time.time() < end_time:
        counter += 1
        _ = counter * counter
    print("[load_simulator] CPU load finished cleanly.")


def allocate_memory(megabytes: int, duration: int) -> None:
    print(
        f"[load_simulator] PID={os.getpid()} | Allocating ~{megabytes} MB RAM for {duration}s..."
    )
    # Allocate bytearray in 1 MB chunks so OS commits real physical pages
    chunks = [bytearray(1024 * 1024) for _ in range(megabytes)]
    for chunk in chunks:
        chunk[0] = 1
    time.sleep(duration)
    chunks.clear()
    print("[load_simulator] Memory released cleanly.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Safe resource load simulator for SentinelAI demos.")
    parser.add_argument("--mode", choices=["cpu", "memory"], required=True)
    parser.add_argument("--duration", type=int, default=20, help="Duration in seconds (default: 20)")
    parser.add_argument("--mb", type=int, default=256, help="Megabytes to allocate in memory mode")
    args = parser.parse_args()

    if args.mode == "cpu":
        burn_cpu(args.duration)
    else:
        allocate_memory(args.mb, args.duration)


if __name__ == "__main__":
    main()