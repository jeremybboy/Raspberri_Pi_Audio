# Music agent orchestration — architecture

This document mirrors the **diagram-aligned v0** layout (Cloud, MacBook, Raspberry Pi). Export this diagram as PNG/SVG from [mermaid.live](https://mermaid.live) by pasting the fenced `mermaid` body only.

## Target architecture (v0)

```mermaid
flowchart LR
  subgraph cloud [Cloud]
    DBX["Dropbox_library"]
  end

  subgraph laptop [Your_laptop_MacBook]
    direction TB
    SYNC["Dropbox_desktop_synced_folder"]
    MAN["manifest_json"]
    OLL["Ollama_local_LLM"]
    AGT["Agent_orchestrator_HTTP_to_Pi"]
    SYNC --> MAN
    MAN --> AGT
    OLL --> AGT
  end

  subgraph rpi [Raspberry_Pi_home_LAN]
    direction TB
    API["HTTP_player_API_play_stop"]
    FILES["Audio_files_on_Pi_disk"]
    MPV["mpv_ALSA"]
    USBIF["USB_audio_interface"]
    OUT["Speakers_or_headphones"]
    API --> MPV
    FILES --> MPV
    MPV --> USBIF
    USBIF --> OUT
  end

  DBX -->|"internet_sync"| SYNC
  AGT -->|"WiFi_or_Ethernet_HTTP"| API
  AGT -.->|"one_time_USB_or_scp"| FILES
```

## Implementation mapping

| Region | Role in code |
|--------|----------------|
| Cloud | Dropbox only; no service in v0. |
| Laptop | `mac/orchestrator_cli.py` reads `manifest.json`, optional Ollama, HTTP to Pi. |
| Raspberry Pi | `pi/player_server.py` (FastAPI), `manifest.json` on disk, `mpv` subprocess. |

See [../README.md](../README.md) for runbook and curl examples.
