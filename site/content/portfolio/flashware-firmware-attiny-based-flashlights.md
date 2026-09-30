---
title: "FlashWare - A firmware for ATTiny based flashlights"
date: "2017-06-02T00:26:27Z"
lastmod: "2017-06-02T00:26:27Z"
slug: "flashware-firmware-attiny-based-flashlights"
tags:
  - "firmware"
  - "flashlight"
---

[FlashWare](https://github.com/Kandepet/FlashWare) is a firmware for my custom LED flashlight running on a 18350/18650 batterys with A17DD-L FET+1 Driver.

Features:

- It is based on ToyKeepers BLF-A6 firmware.
- Currently only supports ATTiny13A.
- Dual channel support only (FET & 7135)
- Uses Fast Pulse Width Modulation
- Supports Off-Time Capacitor for mode selection.
- Modes:
  - Regular Modes: Moonlight, Low, Medium, Turbo
  - Special Modes: STROBE, BIKING\_STROBE, BATTCHECK
- TURBO mode drops down to Medium after 45 seconds.
- Battery Check mode blinks the light 0-10 times to display the state of the battery.
- Mode memory: Last used mode saved to EEPROM. Next start always starts at previous saved mode.
- Voltage monitoring supported to drop flashlight output when battery voltage is low. Low power cutoff switches off the flashlight when voltage drops below 2.7V.

Github: <https://github.com/Kandepet/FlashWare>
