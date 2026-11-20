# Version 1.3.0 (20 November 2026)

## RM126x changes (.806 → .869):

### Added

- SNR and RSSI updated for Join Accepts and ACKs received from LNS (PROD-86940)
- AT+DUTY command extended to support detailed duty cycle queries (PROD-87769)
- Added LORA_TX_IN_PROGRESS synchronous error code (PROD-87773)

### Changed

- Semtech LoRa stack updated to v4.9.0 (PROD-45547)

### Fixed

- Entropy source corrected for channel selection and uplink delays, both are now truly random as opposed to psuedo random (PROD-50345)

### Known Issues:

- P2P mode to be implemented for JP923 (PROD-25017)
- P2P range to be optimised (PROD-25018)

## Firmware changes: none, still 2.1.2

## Application changes (1.2.0 → 1.3.0):

### Added
- **RM126x OTA update over BLE.** Write the firmware image to `/update/rm126x.bin` and it is applied at the next boot. (PROD-83934)
- **BLE advertising time parameter.** This new parameter sets how long the device advertises over BLE after a reset. Changing it to a non-zero value also enables BLE advertising automatically. (PROD-79475)
- **Host-side test suite.** It runs under CPython/pytest with stubbed device modules and gates the firmware packaging job in CI. It covers the protocol, reply shapes and the LoRa, BLE (legacy and C-NUS) and UART transports. (PROD-88425)

### Changed
- **C-based NUS implementation.** The BLE Nordic UART Service now uses the C-based implementation. (PROD-88426)
- **Sensor update timer changes take effect immediately.** (PROD-83933)
- **Lower RAM usage.** The permission lists are now tuples, which saves about 3900 bytes of RAM. (PROD-88616)

### Fixed
- **Ambiguous protocol responses.** (PROD-88427)
- **Long BLE responses are now truncated** to fit the packet length. (PROD-79461)

### Release
- Version 1.3.0 bump. (PROD-79476)
