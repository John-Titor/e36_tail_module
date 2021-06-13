#!/usr/bin/env python3
#
# Functional tests for the 7x_e36 tail module firmware.
#
# Test setup:
#
# - 5A power supply
# - programmer/probe connected
# - DO_1 programmable load
# - DO_2 LED to ground
# - DO_3 open
# - DO_4 open
# - AI_1 some value 0-5V
# - KL15 on relay

import argparse
import curses

from messages import *
from interface import *
from logger import Logger

from monitor import do_monitor
from cas_jbe import do_cas_jbe_test
from dde_scan import do_dde_scan_test


parser = argparse.ArgumentParser(description='E36 tail module tester')
parser.add_argument('--interface',
                    type=str,
                    required=True,
                    metavar='INTERFACE_NAME',
                    help='interface name or path')
parser.add_argument('--interface-type',
                    type=str,
                    metavar='INTERFACE_TYPE',
                    default='slcan',
                    help='interface type')
parser.add_argument('--can-speed',
                    type=int,
                    default=125000,
                    metavar='BITRATE',
                    help='CAN bitrate')
parser.add_argument('--no-CAN-at-start',
                    action='store_true',
                    help='disable vehicle CAN emulation at start')
parser.add_argument('--T15-at-start',
                    action='store_true',
                    help='turn on T15 with T30')
parser.add_argument('--verbose',
                    action='store_true',
                    help='print verbose progress information')

actiongroup = parser.add_mutually_exclusive_group(required=True)
actiongroup.add_argument('--monitor',
                         action='store_true',
                         help='interactive monitor')
actiongroup.add_argument('--cas-jbe',
                         action='store_true',
                         help='test the CAS / JBE emulator')
actiongroup.add_argument('--dde-scan',
                         action='store_true',
                         help='test the DDE scan / repeater')


args = parser.parse_args()
interface = None
try:
    interface = CANInterface(args)
    if args.monitor:
        curses.wrapper(do_monitor, interface, args)
    elif args.cas_jbe:
        do_cas_jbe_test(interface, args)
    elif args.dde_scan:
        do_dde_scan_test(interface, args)
except KeyboardInterrupt:
    pass
except ModuleError as err:
    print(f'MODULE ERROR: {err}')
except MessageError as err:
    print(f'MESSAGE ERROR: {err}')
if interface is not None:
    interface.set_power_off()
