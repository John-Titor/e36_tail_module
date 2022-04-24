#!/usr/bin/env python3
#
# Test console for the E36 tail module
#

import time
import argparse
from interface import Interface, ModuleError
from messages import MessageError

from console import Console
from dde import DDE
from status import Status

parser = argparse.ArgumentParser(description='E36 tail module tester')
parser.add_argument('--interface-channel',
                    type=str,
                    metavar='CHANNEL',
                    required=True,
                    help='interface channel name (e.g. for Anagate units, hostname:portname')
parser.add_argument('--bitrate',
                    type=int,
                    default=500,
                    metavar='BITRATE_KBPS',
                    help='CAN bitrate (kBps)')


args = parser.parse_args()
interface = None
try:
    interface = Interface(args)
    interface.set_power_on()
    dde = DDE(interface)
    status = Status(interface)
    console = Console(interface)

    time.sleep(3)
    dde.brake_on()
    time.sleep(2)
    dde.brake_off()
    time.sleep(2)
except KeyboardInterrupt:
    pass
except ModuleError as err:
    print(f'MODULE ERROR: {err}')
except MessageError as err:
    print(f'MESSAGE ERROR: {err}')
if interface is not None:
    interface.set_power_off()
