import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    parser.add_argument("--agent", required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--status", default="OK")
    parser.add_argument("--data", default="{}")
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        data_obj = json.loads(args.data)
    except json.JSONDecodeError:
        data_obj = {"raw": args.data}

    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "event": args.event,
        "status": args.status,
        "data": data_obj,
        "data_hash": sha256_text(json.dumps(data_obj, sort_keys=True))
    }

    trace_path = run_dir / "trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(f"TRACE_WRITTEN {trace_path}")

if __name__ == "__main__":
    main()
