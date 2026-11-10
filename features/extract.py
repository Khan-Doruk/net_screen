#!/usr/bin/env python3
"""Turn labeled captures into one flow table.

Reads every capture listed in data/labels.csv, groups its packets into
bidirectional flows with NFStream, attaches the session label to each flow
and writes a single CSV. Prints a per-app summary of what was collected.

Usage:
    python features/extract.py data/raw data/flows.csv
"""

import argparse
import sys
from pathlib import Path

import pandas as pd
from nfstream import NFStreamer

REPO_ROOT = Path(__file__).resolve().parent.parent
SESSION_COLUMNS = ["label", "condition", "device"]


def extract_capture(pcap_path, splt, min_packets):
    """Flows of one capture as a DataFrame (statistical features + first-packet sequences)."""
    streamer = NFStreamer(
        source=str(pcap_path),
        statistical_analysis=True,
        splt_analysis=splt,
        n_dissections=20,
    )
    flows = streamer.to_pandas()
    if flows is None or flows.empty:
        return pd.DataFrame()
    return flows[flows["bidirectional_packets"] >= min_packets]


def summarize(flows, sessions):
    """Per-label table of sessions, recorded minutes, flows, packets and megabytes."""
    recorded = sessions.groupby("label").agg(
        sessions=("file", "count"),
        devices=("device", "nunique"),
        minutes=("duration_s", lambda s: round(s.sum() / 60, 1)),
    )
    traffic = flows.groupby("label").agg(
        flows=("label", "size"),
        packets=("bidirectional_packets", "sum"),
        megabytes=("bidirectional_bytes", lambda s: round(s.sum() / 1e6, 1)),
    )
    table = recorded.join(traffic, how="left").fillna(0)
    table.loc["TOTAL"] = table.sum()
    table["devices"] = table["devices"].astype(int)
    table.loc["TOTAL", "devices"] = sessions["device"].nunique()
    return table.astype({"sessions": int, "flows": int, "packets": int})


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("raw_dir", type=Path, help="folder with the .pcapng captures")
    p.add_argument("out_csv", type=Path, help="flow table to write")
    p.add_argument("--labels-csv", type=Path, default=REPO_ROOT / "data" / "labels.csv")
    p.add_argument("--splt", type=int, default=20, help="first N packets kept as size/time sequences")
    p.add_argument("--min-packets", type=int, default=2, help="drop flows with fewer packets")
    args = p.parse_args()

    if not args.labels_csv.exists():
        sys.exit(f"{args.labels_csv} not found. Record sessions with capture/capture.py first.")
    sessions = pd.read_csv(args.labels_csv)

    tables, used = [], []
    for row in sessions.itertuples(index=False):
        pcap_path = args.raw_dir / row.file
        if not pcap_path.exists():
            print(f"skip (file missing): {row.file}")
            continue
        flows = extract_capture(pcap_path, args.splt, args.min_packets)
        if flows.empty:
            print(f"skip (no flows): {row.file}")
            continue
        flows.insert(0, "session", row.file)
        for i, col in enumerate(SESSION_COLUMNS, start=1):
            flows.insert(i, col, getattr(row, col))
        tables.append(flows)
        used.append(row.file)
        print(f"{row.file}: {len(flows)} flows")

    if not tables:
        sys.exit("No flows extracted.")

    all_flows = pd.concat(tables, ignore_index=True)
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    all_flows.to_csv(args.out_csv, index=False)

    print(f"\nWrote {len(all_flows)} flows x {all_flows.shape[1]} columns to {args.out_csv}\n")
    print(summarize(all_flows, sessions[sessions["file"].isin(used)]).to_string())


if __name__ == "__main__":
    main()
