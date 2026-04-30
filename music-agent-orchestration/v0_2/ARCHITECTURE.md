# V0.2 architecture — cloud presign flow

This document explains the transition from v0.1 to v0.2.

## v0.1 reference (local bytes on Pi)

```mermaid
flowchart LR
  MacBrowser[Mac_browser]
  Landing[GET_slash_HTML]
  Swagger[Pi_Swagger_docs]
  API[FastAPI_8766]
  MPV[mpv_IPC_ALSA]
  OLED[OLED_meter]
  MacBrowser -->|"http://pi-host:8766"| Landing
  MacBrowser --> Swagger
  Landing --> API
  Swagger --> API
  API --> MPV
  API --> OLED
```

## v0.2 target (catalog + auth in cloud)

```mermaid
flowchart LR
  MacBrowser[Mac_browser]
  PiAPI[Pi_FastAPI_8767]
  LambdaAPI[Lambda_function_URL]
  S3[(S3_private_objects)]
  MPV[mpv_on_Pi]
  OLED[OLED_meter]
  MacBrowser -->|"http://pi-host:8767"| PiAPI
  PiAPI -->|"HTTPS track_id + api_key"| LambdaAPI
  LambdaAPI -->|"presigned_url + title + expiry"| PiAPI
  PiAPI --> MPV
  MPV -->|"HTTPS GET bytes"| S3
  PiAPI --> OLED
```

## Why v0.2 is API-direct instead of HLS/DASH

v0.2 intentionally uses presigned single-object playback for simplicity:

- small catalog and fast validation of control flow
- minimal moving parts (no packaging pipeline, no segment ladder)
- clear security model (short-lived URLs + private bucket)

HLS/DASH remains a future milestone when adaptive bitrate, larger scale, and richer distribution requirements justify packaging complexity. See [`../docs/streaming-notes.md`](../docs/streaming-notes.md).
