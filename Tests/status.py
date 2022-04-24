#!/usr/bin/env python3
#
# Module status monitor
#

import can
from messages import MessageError, MSG_ack, MSG_status_system, MSG_status_voltage_current, MSG_status_faults


class Status(can.Listener):
    def __init__(self, interface):
        self._line = ''
        interface.add_listener(self)
        self._status = dict()

    def on_message_received(self, message):
        try:
            fields = MSG_ack.unpack(message)
            self.update(fields)
        except MessageError:
            pass
        try:
            fields = MSG_status_system.unpack(message)
            self.update(fields)
        except MessageError:
            pass
        try:
            fields = MSG_status_voltage_current.unpack(message)
            self.update(fields)
        except MessageError:
            pass
        try:
            fields = MSG_status_faults.unpack(message)
            self.update(fields)
        except MessageError:
            pass

    def update(self, fields):
        for key, value in fields.items():
            if key not in ['arbitration_id',
                           'is_extended_id',
                           'dlc',
                           'timestamp',
                           'data']:
                self._status[key] = value


    def __str__(self):
        return f'{self._status}'


if __name__ == '__main__':
    import argparse
    import time
    from interface import Interface

    parser = argparse.ArgumentParser(description='E36 tail module status logger')
    parser.add_argument('--interface-channel',
                        type=str,
                        metavar='CHANNEL',
                        required=True,
                        help='interface channel name (e.g. for Anagate units, hostname:portname')
    parser.add_argument('--bitrate',
                        type=int,
                        default=500,
                        metavar='BITRATE_KBPS',
                        help='CAN bitrate (kBps')

    args = parser.parse_args()
    try:
        status = Status(Interface(args))

        print(f'Status @ {args.interface_channel}')
        while True:
            time.sleep(1.0)
            print(f'{status}')
    except KeyboardInterrupt:
        pass
