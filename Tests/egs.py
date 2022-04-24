#!/usr/bin/env python3
#
# EGS emulator
#

import can
from messages import MessageError, MSG_EGS_PID_request, MSG_EGS_PID_response


class PID(object):

    pids = dict()

    def __init__(self, pid_id, reply_len, initial_value=0):
        self._pid_id = pid_id
        self._reply_len = reply_len
        self._value = initial_value
        self.pids[pid_id] = self

    @property
    def value(self):
        val = bytearray(2)
        if self._reply_len == 1:
            pack_into('>B', val, 0, self._value)
        elif self._reply_len == 2:
            pack_into('>H', val, 0, self._value)
        return val

    @classmethod
    def matching(cls, pid_id):
        try:
            return cls.pids[pid_id]
        except KeyError:
            return None


EGS_ACTUAL_GEAR = PID(0x0a, 1)
EGS_SELECTED_GEAR = PID(0x18, 1)
EGS_SUPPLY_VOLTAGE = PID(0x0c, 1)
EGS_OIL_TEMPERATURE = PID(0x01, 1)


class EGS(can.Listener):
    def __init__(self, interface):
        self._interface = interface
        self._interface.add_listener(self)

    def on_message_received(self, message):
        try:
            fields = MSG_EGS_PID_request.unpack(message)
        except MessageError:
            return
        # one we know?
        pid = PID.matching(fields['pid_id'])
        if pid is None:
            return
        # construct reply & send
        rsp = MSG_EGS_PID_response.with_fields(pid_id=fields['pid_id'], pid_value=pid.value)
        self._interface.send(rsp)


if __name__ == '__main__':
    import argparse
    import time
    from interface import Interface

    parser = argparse.ArgumentParser(description='E36 tail module EGS emulator')
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
        egs = EGS(Interface(args))

        print(f'EGS @ {args.interface_channel}')
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
