# Version 1.1.1 (21 January 2026)

## RM126x changes: none, stay with .806

## Firmware changes (2.1.0 → 2.1.2):

* Many changes, primary change affecting the RS26x is the switch to an RTC that will keep running even during a software reset. This allows the RS26x to keep capturing and storing backlog data even when it is rebooting to attempt to re-join the LoRaWAN network.

## Application changes (1.0.3 → 1.1.0):

* Allow long button press to wake from shipping mode PROD-27935
* Start sensor sampling immediately PROD-50060
* Add public key to filesystem PROD-50061
* Rework join timeout PROD-50445
* Refresh RTC time from network periodically PROD-52779
* Use the latest packager tool PROD-52791
* Cannot update to app 1.1.0 with Canvas 2.1.0 PROD-54200
