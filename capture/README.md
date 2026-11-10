# Capture setup (Windows laptop)

The laptop must be the hotspot. A phone's own hotspot does not work: the phone's traffic would never pass through the laptop, so there would be nothing to capture.

```
Phone ──Wi-Fi──> Laptop (Mobile hotspot) ──Wi-Fi or Ethernet──> dorm / home internet
```

## One-time setup

1. Install [Wireshark](https://www.wireshark.org/download.html). Keep **TShark** and **Npcap** ticked in the installer.
2. Install the Python packages: `pip install -r requirements.txt`
3. Connect the laptop to the internet as usual (Wi-Fi or Ethernet).
4. Settings > Network & internet > Mobile hotspot: turn it on. Note the network name and password.
5. Find the hotspot interface. It is the one named `Local Area Connection* <number>`:

   ```
   python capture/capture.py --list-ifaces
   ```

   If there are several, `ipconfig` shows which one has the address `192.168.137.1`.

## Recording a session

1. Join the phone to the laptop's hotspot.
2. On the phone turn off VPN and iCloud Private Relay, and close other apps.
3. Read the phone's IP address from the Mobile hotspot settings page (connected devices list, `192.168.137.x`).
4. Start the recording, then open the app and keep using it until the script finishes:

   ```
   python capture/capture.py --iface "Local Area Connection* 10" --label youtube --device doruk-iphone --phone-ip 192.168.137.23 --minutes 5
   ```

Several phones can be recorded at the same time, one terminal per phone, each with its own `--phone-ip`, `--device` and `--label`.

Labels: `youtube`, `tiktok`, `instagram`, `netflix`, `gaming`, `messaging`, `videocall`, `idle` (phone connected, screen off).

## After recording

```
python features/extract.py data/raw data/flows.csv
```

This writes the flow table and prints sessions, minutes, flows, packets and megabytes per app. Captures stay in `data/raw/` (not committed); `data/labels.csv` is committed.
