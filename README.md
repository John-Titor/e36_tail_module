# "Hello Kitty" BMW E36 / M57 race car tail module

This is firmware for an MRS Microplex 7X installed in an M57-swapped BMW E36 M3. It implements the following functions:

 - Brake, tail and rain light management.
 - Fuel level sensing / reporting.
 - DDE and EGS parameter reading and reformatting.

## System

The vehicle electronic system consists of this module, the M57 DDE, ZF 6HP transmission controller (EGS), fuel pump controller (EKPM), MK60 ABS, and an AiM PDM08.

## Lights

Brake lights are controlled directly by the CAN brake switch signal sent by the DDE.

Tail and rain lights are controlled by bits in a custom CAN stream sent by the PDM08.

## Fuel

The fuel level sensor in the fuel cell produces a 0.5-4.5V signal from empty to full; this is sampled by firmware, smoothed and the resulting value sent via CAN to the PDM08

## DDE / EGS parameter extraction

Firmware uses the BMW parameter reading protocol to query DDE and EGS parameters, then reports these in a fashion that the PDM08 can handle.

The BMW parameter protocol is essentially their K-line protocol encapsulated in ISO-TP https://en.wikipedia.org/wiki/ISO_15765-2 frames with extended addressing. To keep things simple, we only query a single PID per message.

### DDE query frame format

XXX is this correct? is there a more compact query format?

CAN ID | Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7
------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------
0x6f1  | ECU ID | length | 0x2c   | 0x10   | PID0   | PID1   | 0x00   | 0x00

ECU ID : 0x12 = DDE, 0x18 = EGS
length : 5..7 depending on the length of PID data
PIDx   : PID bytes (see below)

### DDE response frame format

CAN ID | Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4..7
------ | ------ | ------ | ------ | ------ | ---------
ECU ID | 0xf1   | length | 0x6c   | 0x10   | Data 0..3

ECU ID : 0x612 = DDE, 0x618 = EGS
length : 5..7 depending on the length of the data
Data   : parameter data, unused bytes are 0xff

### DDE PIDs

PID0 | PID1 | response | description
---- | ---- | -------- | -----------
0x03 | 0x85 | TH TL    | fuel temperature in °C = (TH:TL / 100) - 55
0x04 | 0x1b | TH TL    | exhaust temperature in °C = (TH:TL / 32) - 50
0x07 | 0x6f | TH TL    | manifold air temperature in °C = (TH:TL / 100) - 100
0x07 | 0x6d | PH PL    | PH:PL = manifold pressure in mBar
0x0a | 0x8d | SS       | oil pressure status, 00 = OK, 01 = low oil pressure
0x0e | 0xa6 | GG       | current gear = GG
0x10 | 0x06 | SS       | MIL indicator status

### EGS query frame format

CAN ID | Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7
------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------
0x6f1  | 0x18   | 0x02   | 0x21   | PID    | 0x00   | 0x00   | 0x00   | 0x00

### EGS response frame format

CAN ID | Byte 0 | Byte 1 | Byte 2 | Byte 3 | Byte 4 | Byte 5 | Byte 6 | Byte 7
------ | ------ | ------ | ------ | ------ | ------ | ------ | ------ | ------
0x618  | 0xf1   | 0x03   | 0x61   | PID    | 0x00   | 0x00   | 0x00   | 0x00

### EGS PIDs

PID  | response | description
---- | -------- | -----------
0x01 | TT       | EGS oil temperature (0x43 = ambient, perhaps °C - 50) XXX verify
0x0a | GG       | actual gear (GG = gear)
0x0b | LL       | EGS lockup (00 = not locked up)
0x0c | VV       | T30 voltage (0xae ~= 14v) XXX test
0x18 | SS       | selected gear (1 "P" 2 "R" 4 "N" 8 "D") XXX verify
0x1a | LL       | limp mode (89 = in limp mode)