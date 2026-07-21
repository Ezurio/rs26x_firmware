# Version 1.0.0 (12 March 2025)

## Firmware changes (0.4.2 → 2.0.1):

* Updates for reworked timer API. PROD-3532
* Update to Simplicity SDK 2024.6.2. PROD-17016
* Add extra delay after flash wake-up. PROD-21281
* Rework configuration file includes. PROD-14704
* Add name for PA09 for RS2xx. PROD-21469

## RM126x changes: none, use .729

## Application changes (0.4.3 → 1.0.0):

* Update external thermistor coefficients, PROD-6707
* Handle re-detection of sensor if not plugged in at power-up, PROD-15109 PROD-17633
* Implement a low battery lockout and configurable battery thresholds, PROD-14361
* Don't reboot RS26x on error if BLE is connected, PROD-21620
* Change device model to RS26x, PROD-22219
* Fix handling of backlog available flag, PROD-22242
* Support reading raw battery voltage, PROD-22249
