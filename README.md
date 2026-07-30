# APRS-WinTAK Gateway

A robust, bi-directional Python/Tkinter gateway that bridges analog APRS (via SoundModem/KISS over TCP) with WinTAK/ATAK using a local TCP Cursor-on-Target (CoT) server architecture. 

This tool allows you to track APRS stations on your WinTAK map with custom icons, receive APRS text messages directly into WinTAK GeoChat, and reply to them—automatically encoding and transmitting AX.25 packets out of your HF/VHF/UHF transceiver.

## Features

* **Live Position Tracking:** Parses incoming APRS coordinate packets and injects CoT position markers into WinTAK with custom icon mapping and whitelisting.
* **Bi-Directional Messaging:** 
  * **RX:** Inbound APRS text messages pop up natively inside WinTAK GeoChat linked to the correct contact marker.
  * **TX:** Outbound GeoChat replies from WinTAK are intercepted by the local gateway, encoded into valid AX.25 UI frames, and pushed via KISS to SoundModem to key up your radio.
* **True TAK Server Architecture:** Emulates a local TCP CoT server to maintain a stable, persistent connection with WinTAK, preventing dropouts and managing XML data streams seamlessly.
* **Heartbeat & Buffering:** Includes automatic server keep-alives (pings) and robust TCP stream buffering to handle segmented XML packets cleanly.

## Prerequisites

1. **WinTAK** running on the same Windows machine.
2. **SoundModem** (or an equivalent KISS-compatible TNC software) configured and connected to your radio interface (e.g., Signalink or sound card) on a local TCP KISS port (default: `8001`).

## Installation & Requirements

The project relies exclusively on Python's built-in standard libraries (Sockets, Threading, XML ElementTree, Re), meaning no heavy external dependencies are required.

1. Ensure Python 3.x is installed on your system.
2. Clone or download this repository.

```bash
git clone [https://github.com/your-username/aprs-wintak-gateway.git](https://github.com/your-username/aprs-wintak-gateway.git)
cd aprs-wintak-gateway
```

##Run the application:

```Bash
python aprs_wintak_gui.py
```

##Configuration Guide

1. Configure WinTAK Server Connection
Because this script acts as a local TAK Server, you must point WinTAK to it:

Open WinTAK.

Navigate to Settings -> Network Preferences -> Manage Server Connections.

Click Add and configure the connection:

Description: Local APRS Bridge

Protocol: TCP (Make sure this is TCP, not SSL or UDP)

Host Address: 127.0.0.1

Port: 8080

Click OK and ensure the connection status is toggled ON.

2. Configure the Gateway App
Launch aprs_wintak_gui.py.

Enter your station's My Callsign (TX) (e.g., K5JGL-1).

Verify your SoundModem host and KISS port settings (default is 127.0.0.1 and 8001).

Click Start Bridge.

Once connected, WinTAK will handshake with the local server, and the connection status will turn green.

##Usage
Mapping Stations: Add callsigns to the whitelist panel with your preferred WinTAK icon type (e.g., Civilian Vehicle, Ground Unit), or check "Map ALL Callsigns" to automatically map every heard station.

Receiving/Sending Messages: When a station transmits an APRS message over the air, it will appear in both the app's APRS Messages tab and WinTAK's chat window. To reply, simply open the contact's chat in WinTAK, type your response, and hit send—the gateway will handle the AX.25 formatting and trigger your radio's PTT.

##License
This project is open-source and distributed under the MIT License.
