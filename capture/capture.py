#!/usr/bin/env python3
"""Record one labeled capture session with tshark.

One session = one phone using one app for a fixed time. The packets go to
data/raw/<label>__<condition>__<device>__<timestamp>.pcapng and one row
describing the session is appended to data/labels.csv.

Examples:
    python capture/capture.py --list-ifaces
    python capture/capture.py --iface wlan0 --label youtube --device doruk-iphone \
        --phone-ip 192.168.137.23 --minutes 5
"""

import argparse
import csv
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

LABELS = [
    "youtube",
    "tiktok",
    "instagram",
    "netflix",
    "gaming",
    "messaging",
    "videocall",
    "idle",  # phone connected, screen off: background traffic only
]
CONDITIONS = ["plain", "doh", "vpn"]
LABEL_COLUMNS = [
    "file",
    "label",
    "condition",
    "device",
    "phone_ip",
    "phone_mac",
    "start_utc",
    "duration_s",
    "notes",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
WINDOWS_TSHARK = Path(r"C:\Program Files\Wireshark\tshark.exe")


def find_tshark():
    path = shutil.which("tshark")
    if path:
        return path
    if WINDOWS_TSHARK.exists():
        return str(WINDOWS_TSHARK)
    sys.exit("tshark not found. Install Wireshark (with tshark) and put it on PATH.")


def capture_filter(phone_ip, phone_mac):
    """BPF filter that keeps only the phone's traffic. MAC also covers IPv6."""
    parts = []
    if phone_ip:
        parts.append(f"host {phone_ip}")
    if phone_mac:
        parts.append(f"ether host {phone_mac}")
    return " or ".join(parts)


def append_label_row(labels_csv, row):
    labels_csv.parent.mkdir(parents=True, exist_ok=True)
    is_new = not labels_csv.exists() or labels_csv.stat().st_size == 0
    with labels_csv.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LABEL_COLUMNS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--list-ifaces", action="store_true", help="list capture interfaces and exit")
    p.add_argument("--iface", help="hotspot interface name or number from --list-ifaces")
    p.add_argument("--label", choices=LABELS, help="app used during the session")
    p.add_argument("--device", help="short phone name without spaces, e.g. doruk-iphone")
    p.add_argument("--condition", choices=CONDITIONS, default="plain")
    p.add_argument("--minutes", type=float, default=5.0, help="session length (default 5)")
    p.add_argument("--phone-ip", help="phone's IP on the hotspot; captures only this phone")
    p.add_argument("--phone-mac", help="phone's MAC on the hotspot; captures only this phone")
    p.add_argument("--snaplen", type=int, default=0, help="bytes kept per packet, 0 = whole packet")
    p.add_argument("--notes", default="", help="free text, e.g. '1080p video' or 'Brawl Stars'")
    p.add_argument("--out-dir", type=Path, default=REPO_ROOT / "data" / "raw")
    p.add_argument("--labels-csv", type=Path, default=REPO_ROOT / "data" / "labels.csv")
    args = p.parse_args()
    if not args.list_ifaces:
        missing = [n for n in ("iface", "label", "device") if getattr(args, n) is None]
        if missing:
            p.error("missing: " + ", ".join("--" + n for n in missing))
        if "__" in args.device or any(c in args.device for c in " /\\"):
            p.error("--device must not contain spaces, slashes or '__'")
        if args.minutes <= 0:
            p.error("--minutes must be positive")
    return args


def main():
    args = parse_args()
    tshark = find_tshark()

    if args.list_ifaces:
        return subprocess.call([tshark, "-D"])

    start = datetime.now(timezone.utc)
    stamp = start.strftime("%Y%m%d-%H%M%S")
    name = f"{args.label}__{args.condition}__{args.device}__{stamp}.pcapng"
    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / name
    seconds = int(round(args.minutes * 60))

    cmd = [tshark, "-i", args.iface, "-w", str(out_path), "-a", f"duration:{seconds}", "-q"]
    bpf = capture_filter(args.phone_ip, args.phone_mac)
    if bpf:
        cmd += ["-f", bpf]
    else:
        print("WARNING: no --phone-ip/--phone-mac, capturing every device on the interface.")
    if args.snaplen:
        cmd += ["-s", str(args.snaplen)]

    print(f"Recording {args.label} ({args.condition}) on {args.device} for {seconds} s")
    print(f"  -> {out_path}")
    print("Open the app now and keep using it until this finishes. Ctrl+C stops early.")

    t0 = time.monotonic()
    proc = subprocess.Popen(cmd)
    try:
        proc.wait()
    except KeyboardInterrupt:
        # Let tshark flush the file; on Windows it already got the Ctrl+C itself.
        if os.name != "nt":
            proc.send_signal(signal.SIGINT)
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("\nStopped early.")
    duration = round(time.monotonic() - t0)

    size = out_path.stat().st_size if out_path.exists() else 0
    if size == 0:
        sys.exit("No packets were written. Check the interface name, permissions and filter.")

    append_label_row(
        args.labels_csv,
        {
            "file": name,
            "label": args.label,
            "condition": args.condition,
            "device": args.device,
            "phone_ip": args.phone_ip or "",
            "phone_mac": args.phone_mac or "",
            "start_utc": start.isoformat(timespec="seconds"),
            "duration_s": duration,
            "notes": args.notes,
        },
    )
    print(f"Saved {size / 1e6:.1f} MB in {duration} s, logged in {args.labels_csv}")
    if size < 50_000:
        print("WARNING: very small capture. Was the phone using the app on this hotspot?")


if __name__ == "__main__":
    sys.exit(main())
