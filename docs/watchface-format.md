# Table Face Package Format (v0.1 Draft)

This document defines the agreement between the "face store mini-program" and the hardware.
It is currently in draft stage; only the BLE channel has been implemented and verified,
while the data stream feature (...0005 DATA) is reserved pending implementation in milestone 2.

---

## 1. Overall Form

A table face = `watchface.json` (metadata) + `frames.bin` (pixel frames)

One table face package `face_pkg.zip`:

```
face_pkg.zip
├── manifest.json        # metadata + frame index + checksum
└── frames.bin           # concatenated pixel frame data, RGB565, little-endian
```

### 1.1 manifest.json

```json
{
  "id": "cat_drinking_tea",
  "name": "Peppercat Drinking Tea",
  "author": "dada",
  "version": 1,
  "width": 64,
  "height": 64,
  "pixel_format": "RGB565",
  "bg_mode": "transparent",
  "frame_count": 4,
  "fps": 4,
  "loop": true,
  "duration_ms": 1000,
  "checksum": "crc32-frames-9a3f21b0",
  "sign": "optional-ed25519-signature",
  "created": "2026-10-21",
  "min_fw": "0.2.0"
}
```

Field descriptions:
- `bg_mode`: `transparent` = dark pixels do not overwrite background
  (making it a dial that can overlay dates/times); `opaque` = full overwrite.
- `fps` + `frame_count` → playback frame rate; `duration_ms = frame_count * 1000 / fps`
- `checksum`: CRC32 of frames.bin; firmware verifies after receiving.
- `sign`: v0.2 will support author signature, preventing malicious face packages
  (recorded in the format spec; not mandatory for now).

### 1.2 frames.bin

Pixel stream, row-major, RGB565 little-endian:

```
offset 0:   frame0, 64*64*2 = 8192 bytes
offset 8K:  frame1, 8192 bytes
...
```

`bg_mode=transparent` means: when a pixel's RGB565 value equals `0x0000`,
it is treated as "do not draw", letting the time/date layer show through.

---

## 2. BLE Transmission Protocol (DATA feature ...0005)

Firmware as GATT Server, mini-program as GATT Client.
Frame count is large (64×64×2×N), needs paging + checksum:

### 2.1 General Frame Format

```
[1 byte magic 0xA5][1 byte type][1 byte seq][1 byte len][payload...][2 bytes crc16]
```

- `type`: see table below
- `seq`: segment number 0~255, modulo 256; retransmit uses the same seq
- `len`: payload length (MTU after negotiation - 6; typically 244)
- `crc16`: checksum of the entire frame (after magic)

### 2.2 Command Types

| type | Direction | Function | Payload |
|---|---|---|---|
| 0x01 | App→FW | Start transmission | manifest.json content (JSON plaintext) |
| 0x02 | App→FW | Data segment | frames.bin slice (seq from 0 in sequence) |
| 0x03 | App→FW | End | total segment count (uint16) |
| 0x04 | FW→App | ACK | seq (acknowledge receipt, ready for next) |
| 0x81 | FW→App | NAK | seq (checksum failed, wait for retransmit) |
| 0x82 | FW→App | Done | new face id string (checksum + write complete) |

### 2.3 Transmission Flow

```
App                          Firmware
 | 0x01 START (manifest) ---> |  verify parameters / erase Flash target area
 |                            | <--- 0x04 seq=0xFF (ready)
 | 0x02 DATA seq=0 ---------> |  verify crc16 → write to Flash
 |                            | <--- 0x04 seq=0
 | 0x02 DATA seq=1 ---------> |
 |                            | <--- 0x04 seq=1
 | ...                        |
 | 0x03 END count=N --------> |  verify full-package CRC32
 |                            | <--- 0x82 "id"  (success, registered into face list)
 |  App displays "Delivery complete"    |
```

### 2.4 Verification

After receiving all segments:

1. **Segment CRC16** (defends transmission corruption)
2. **Full-package CRC32** (against manifest.checksum)
3. Reject if neither matches → save old data and reply 0x81

### 2.5 Firmware Storage Strategy

- New repo: Each face package occupies a Flash slot (say 64KB, can hold 8 frames);
  faces during the build phase are externally connected and registered into
  the face registry by `FACE` feature switching.
- Slot manager: delete/overwrite by `id`; a table in NVS records
  `{slot, id, version, valid_crc}`.
- Restore factory face selections when user data area is corrupted.

---

## 3. Mini-Program Side Division of Labor (Split by Milestone)

| Milestone | Content | This Engineering Corresponding Part |
|---|---|---|
| M2 | BLE time sync + face switching | ✅ Time/Face features already in use |
| M3 | Table face package sending (this protocol) | DATA feature + Flash slot manager |
| M4 | Table face store (backend + payment) | Not firmware scope |

## 4. Unfinished/Needs Decision Items

1. `RGB565` pixel format RGB order: this doc specifies `R(5)<<11 | G(6)<<5 | B(5)`.
   Generation-side conversion tool (tools/mkface.py) needs unified implementation.
2. Whether MTU requires requesting 517 bytes at app connection (affects transmission speed).
3. Signature algorithm: ED25519 vs HMAC, to be determined after M3.
