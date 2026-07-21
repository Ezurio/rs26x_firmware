# Version 0.4.2 (20 November 2024)

The new firmware in this version (0.4.2) uses different signing keys than the previous builds. This makes this version not compatible for OTA upgrades in either direction. This firmware version requires programming via SWD.

## Firmware changes (0.3.3 → 0.4.2):

* Firmware builds are now signed with unique keys
* Script signing key added to RS2xx build
* Added memoryview, re, select, and asyncio modules to MicroPython

## Application changes (0.4.0 → 0.4.2):

* Fix button handling to remove occasional extra reset, PROD-16251
* Create a ECDSA signed script package, currently both original SHA256 and ECDSA ZIP files are being generated. Eventually, the SHA256 version will be removed. Version 0.4.2 of the RS2xx firmware is required to use the ECDSA script package. PROD-12049
* Change the application startup message to be more clear, PROD-16665
* Fix protocol issues with setting AppKey, PROD-16934
* Allow empty Friendly Name, PROD-16916
* Change BLE advertisement to include DevEUI, PROD-16735

## RM126x changes: none
