# Version 1.2.0 (25 June 2026)

## RM126x changes: none, stay with .806

## Firmware changes: none, still 2.1.2

## Application changes (1.1.1 → 1.2.0):

* Support RTD probe. 
    * PROD-41898: RTD Probe Canvas Driver Support 
    * PROD-59007: Create a test for RTD and thermistor probes
    * PROD-63877: Adjust RS26x RTD conversion equation

* Switch to C-based backlog implementation.
    * PROD-53832: Switch to C-based flash backlog
    * PROD-58100: Backlog export takes too long and trips watchdog

* Corrected behavior of “Backlog Available” and “Bandwidth Limited” status flags.
    * PROD-68935: RS26x reports "Backlogs Available" flag incorrect in Aggregated mode

* Keep “Backlog Wraparound” status flag in non-volatile memory so the condition can persist a power-cycle.
    * PROD-74086: Store backlog wrap-around flag in non-volatile memory

* Adjusted ADC calibration and Steinhart-Hart coefficients for external thermistor to improve temperature accuracy.
    * PROD-74585: RS26x poor performance at low temperatures
 
* Read battery voltage at power-up so battery status can be reported before the first LoRaWAN transmit.
    * PROD-75371: Fetch battery manually at power-up

* Miscellaneous fixes
    * PROD-16976: Finish one-wire support
    * PROD-66736: Update RS26x action for Node.js 20 deprecation
    * PROD-73656: RS26x exception when reading external sensor when not connected
    * PROD-74074: RS26x update rate can be set to 5 seconds
 
