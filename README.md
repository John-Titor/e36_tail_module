# "Hello Kitty" BMW E36 / M57 race car tail module

This is firmware for an MRS Microplex 7X installed in an M57-swapped BMW E36 M3. It implements the following functions:

 - Brake, tail and rain light management.
 - Fuel level sensing / reporting.
 - DDE (and in future EGS) parameter reading and reformatting.
 - ~~CAS and JBE emulation to support BimmerGeeks ProTool and the XHP transmission tuning tool.~~

## System

The vehicle electronic system consists of this module, the M57 DDE, ZF 6HP transmission controller (EGS), fuel pump controller (EKPM), MK60 ABS, and an AiM PDM08.

## Lights

Brake lights are controlled directly by the CAN brake switch signal sent by the DDE.

Tail and rain lights are controlled by bits in a custom CAN stream sent by the PDM08.

## Fuel

The fuel level sensor in the fuel cell produces a 0.5-4.5V signal from empty to full; this is sampled by firmware, smoothed and the resulting value sent via CAN to the PDM08

## DDE / EGS parameter extraction

Firmware uses the BMW parameter reading protocol to query DDE and EGS parameters, then reports these in a fashion that the PDM08 can handle.

## CAS / JBE emulation

ProTools (and other BMW scan tools) expect to be able to fetch vehicle configuration data from the CAS module. This emulation provides just enough fidelity to enable the specific tools of interest.
