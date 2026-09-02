#!/usr/bin/env python3
"""One-shot: backup live Ladder JSON and write sanitized fixtures for GitHub."""

import json
import re
import shutil
from pathlib import Path

LADDER = Path(__file__).resolve().parent.parent / "Ladder"
LIVE = LADDER / "_live_data"
FIXTURE_FILES = [
    "elo.json",
    "elodahv.json",
    "dodges.json",
    "ongoing.json",
    "parameters.json",
    "banned_players.json",
    "match_record.json",
]
SNAPSHOT_GLOB = "elodahv_*.json"

SNOWFLAKE = re.compile(r"\b\d{17,20}\b")


def collect_ids_from_obj(obj, found: set[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(k, str) and k.isdigit() and len(k) >= 17:
                found.add(k)
            collect_ids_from_obj(v, found)
    elif isinstance(obj, list):
        for item in obj:
            collect_ids_from_obj(item, found)
    elif isinstance(obj, (int, str)):
        s = str(obj)
        if s.isdigit() and len(s) >= 17:
            found.add(s)


def remap_obj(obj, mapping: dict[str, str]):
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            nk = mapping.get(k, k) if isinstance(k, str) else k
            out[nk] = remap_obj(v, mapping)
        return out
    if isinstance(obj, list):
        return [remap_obj(x, mapping) for x in obj]
    if isinstance(obj, int):
        s = str(obj)
        return int(mapping[s]) if s in mapping else obj
    if isinstance(obj, str) and obj.isdigit() and len(obj) >= 17 and obj in mapping:
        return mapping[obj]
    return obj


def main() -> None:
    LIVE.mkdir(parents=True, exist_ok=True)

    all_ids: set[str] = set()
    sources: dict[str, Path] = {}

    for name in FIXTURE_FILES:
        src = LADDER / name
        if src.exists():
            sources[name] = src
            if name == "match_record.json":
                for line in src.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        collect_ids_from_obj(json.loads(line), all_ids)
            elif name == "banned_players.json":
                collect_ids_from_obj(json.loads(src.read_text(encoding="utf-8")), all_ids)
            else:
                collect_ids_from_obj(json.loads(src.read_text(encoding="utf-8")), all_ids)

    for snap in LADDER.glob(SNAPSHOT_GLOB):
        shutil.copy2(snap, LIVE / snap.name)

    mapping = {
        old: str(100_000_000_000_000_000 + i)
        for i, old in enumerate(sorted(all_ids, key=int))
    }

    for name, src in sources.items():
        shutil.copy2(src, LIVE / name)
        if name == "match_record.json":
            lines = []
            for line in src.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                lines.append(
                    json.dumps(remap_obj(json.loads(line), mapping), separators=(",", ": "))
                )
            (LADDER / name).write_text("\n".join(lines) + "\n", encoding="utf-8")
        else:
            data = json.loads(src.read_text(encoding="utf-8"))
            out = remap_obj(data, mapping)
            (LADDER / name).write_text(json.dumps(out, indent=4) + "\n", encoding="utf-8")

    for snap in LADDER.glob(SNAPSHOT_GLOB):
        snap.unlink()

    # Safe demo banned list
    (LADDER / "banned_players.json").write_text(
        json.dumps(["100000000000000099"], indent=4) + "\n", encoding="utf-8"
    )

    print(f"Backed up live data to {LIVE}")
    print(f"Remapped {len(mapping)} Discord user IDs to synthetic fixtures")


if __name__ == "__main__":
    main()
