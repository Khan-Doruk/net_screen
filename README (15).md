# NetScreen

**Network-level screen-time monitoring via encrypted traffic classification, with an ESP32 alert device.**

ECE 422 Computer Communications and Networks, Fall 2026, NJIT. Term project.

Team: Dorukhan Cakir, Asmar Hasanova, Yusuf Bilal Cetinkaya, Semih Karaismailoglu

## What it does

NetScreen tells which application a phone is using (YouTube, TikTok, Instagram, Netflix, games, messaging) by looking only at the **shape** of its Wi-Fi traffic: packet sizes and timing. It never reads packet contents and nothing is installed on the phone.

1. Phones join a laptop running as a Wi-Fi hotspot.
2. The laptop captures packets, groups them into flows and classifies each flow.
3. A per-device, per-app clock is kept and shown on a web dashboard.
4. When a device passes its limit (for example 60 minutes of video a day), an MQTT message is published and an ESP32 with an OLED screen, LED and buzzer raises the alert.

## Why

Classic application detection reads plain-text clues: the domain name in DNS, or the server name (SNI) in the TLS handshake. TLS 1.3, QUIC, DNS-over-HTTPS and VPNs are removing those clues. Operators, companies and parents still need to know which apps are in use, for QoS, policy and screen-time limits. Industry systems such as Cisco NBAR2 and Encrypted Traffic Analytics already classify encrypted flows by packet size and timing. NetScreen is a small-scale, measurable version of that idea.

## Research question

We compare three detection methods under three conditions:

| Method | Plain Wi-Fi | Encrypted DNS (DoH) | VPN |
|---|---|---|---|
| DNS name lookup | works | fails | fails |
| TLS SNI | works | works | fails |
| ML on flow shape (ours) | works | works | measured |

We report accuracy per app, detection latency (seconds from app launch to correct label), false-alarm rate, and how each method degrades as encryption increases.

## Architecture

```
Phones ──Wi-Fi──> Laptop hotspot ──> Internet
                      │
                 capture (tshark)
                      │
                 flows + features (NFStream)
                      │
          ┌───────────┼───────────┐
        DNS          SNI        ML model
          └───────────┼───────────┘
                      │
              per-device clock + FastAPI backend
                      │
          ┌───────────┴───────────┐
     React dashboard         MQTT broker ──> ESP32 (OLED, LED, buzzer)
```

## Repository layout

```
netscreen/
├── capture/        tshark capture scripts, hotspot setup notes
├── features/       flow extraction with NFStream, feature definitions
├── models/         DNS and SNI baselines, Random Forest / XGBoost / 1D CNN training
├── backend/        FastAPI service: live classification, per-device clocks, MQTT publisher
├── dashboard/      React + Vite web dashboard
├── firmware/       ESP32 code (Arduino / PlatformIO): MQTT subscriber, OLED, buzzer
├── data/           collected captures and labels (large files are git-ignored)
├── experiments/    evaluation notebooks and result tables
├── docs/           report drafts, slides, diagrams
└── README.md
```

## Dataset

We record our own data. Each team member uses one app for a fixed session (about 10 minutes) on their own phone connected to the hotspot; the capture is labeled with that app. Sessions are repeated across phones and times of day, and again with DNS-over-HTTPS on and with a VPN on. Only our own devices are captured.

The public ISCX VPN-nonVPN 2016 dataset is used as a cross-check for the VPN scenario.

## Models

- Baselines: DNS lookup, TLS SNI matching
- Features per flow: packet size statistics, inter-arrival times, burst length, upload/download ratio, flow duration
- Classifiers: Random Forest and XGBoost first, then a 1D CNN on raw packet-size sequences

## Hardware

- 1 laptop as hotspot and classifier
- 1 ESP32 DevKit (plus one spare)
- 0.96 inch SSD1306 OLED (I2C), active buzzer, LED

Stretch goal: run the ESP32 in Wi-Fi promiscuous mode as a standalone sniffer that sees 802.11 frame sizes and timing without joining the network.

## Setup (to be completed as the code lands)

```bash
# Python side
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# capture on the hotspot interface
python capture/capture.py --iface <hotspot-interface> --label tiktok --minutes 10

# extract features and train
python features/extract.py data/raw data/flows.csv
python models/train.py data/flows.csv

# run backend and dashboard
uvicorn backend.main:app --reload
cd dashboard && npm install && npm run dev
```

ESP32 firmware lives in `firmware/` and is built with PlatformIO. Set the Wi-Fi and MQTT broker credentials in `firmware/config.h`.

## Timeline

| Date | Milestone |
|---|---|
| Oct 30 | 500-word project summary |
| Nov 5 | Capture setup running, first labeled dataset |
| Nov 19 | DNS/SNI baselines, trained ML model |
| Dec 1 to 5 | DoH/VPN tests, ESP32 alert, final presentation and demo video |
| Dec 11 | Final report |

## Ethics

Only the team's own devices are monitored, with consent, on a private test network. No traffic from other users is captured.

## References

Initial list, to be extended in the final report:

- G. Draper-Gil, A. H. Lashkari, M. S. I. Mamun, A. A. Ghorbani, "Characterization of Encrypted and VPN Traffic Using Time-Related Features," ICISSP 2016.
- W. Wang, M. Zhu, J. Wang, X. Zeng, Z. Yang, "End-to-end encrypted traffic classification with one-dimensional convolution neural networks," IEEE ISI 2017.
- B. Anderson, D. McGrew, "Identifying Encrypted Malware Traffic with Contextual Flow Data," AISec 2016 (basis of Cisco Encrypted Traffic Analytics).
- Cisco, "Encrypted Traffic Analytics" white paper.
- IETF RFC 8484, DNS Queries over HTTPS (DoH).
- IETF RFC 9000, QUIC: A UDP-Based Multiplexed and Secure Transport.
- OASIS, MQTT Version 5.0 specification.
