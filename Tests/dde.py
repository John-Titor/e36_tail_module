#!/usr/bin/env python3
#
# DDE emulator
#

import time
import can
from messages import *


# class PID(object):
# 
#     pids = dict()
# 
#     def __init__(self, pid_id, reply_len, initial_value=0):
#         self._pid_id = pid_id
#         self._reply_len = reply_len
#         self._value = initial_value
#         self.pids[pid_id] = self
# 
#     @property
#     def value(self):
#         val = bytearray(2)
#         if self._reply_len == 1:
#             pack_into('>B', val, 0, self._value)
#         elif self._reply_len == 2:
#             pack_into('>H', val, 0, self._value)
#         return val
# 
#     @classmethod
#     def matching(cls, pid_id):
#         try:
#             return cls.pids[pid_id]
#         except KeyError:
#             return None
# 
# 
# DDE_AMBIENT_TEMPERATURE = PID((0x0f, 0xd2), 2, 0x0b2a)          # 12.7°C
# DDE_INTAKE_AIR_TEMPERATURE = PID((0x07, 0x71), 2, 0x1a3c)       # 17.16°C
# DDE_CHARGE_AIR_TEMPERATURE = PID((0x07, 0x6f), 2, 0x2c34)       # 13.2°C
# # 0x176c = -40.04°C
# DDE_EXHAUST_TEMPERATURE = PID((0x04, 0x2e), 2, 0x0799)          # 10.8°C
# # 0x013e = -40.1°C
# DDE_FUEL_TEMPERATURE = PID((0x03, 0x85), 2, 0x1a64)             # 17.5°C
# DDE_FILTERED_OIL_TEMPERATURE = PID((0x04, 0x58), 2, 0x2bde)     # 12.3°C
# # trans oil temp?
# 
# DDE_AMBIENT_PRESSURE = PID((0x0c, 0x1c), 2, 0x7d2e)             # 1bar (rounding?)
# DDE_CHARGE_AIR_PRESSURE = PID((0x06, 0x6d), 2)
# DDE_BOOST_PRESSURE = PID((0x07, 0x7d), 2, 0x2a11)               # -0.03 (rounding?)
# # 0x2666 = 0.9 / -0.11
# # 0x2a3d = 987.97mBar
# DDE_OIL_WARNING_STATUS = PID((0x0a, 0x8d), 2)
# 
# DDE_SUPPLY_VOLTAGE = PID((0x02, 0x2c), 2)
# DDE_BATTERY_VOLTAGE = PID((0x01, 0x2c), 2, 0x79ac)              # 12119.84mV
# # 0x7912 = 12059.9mV
# # 0x7844 = 11979mV
# # also PID 0x01, 0x2d?
# 
# DDE_CURRENT_GEAR = PID((0x0e, 0x86), 1, 0)                      # P?
# DDE_CURRENT_INTERNAL_GEAR = PID((0x06, 0xf6), 1, 0)             # P?
# DDE_FAN_DUTY_RATIO = PID((0x09, 0xc4), 2, 0xe665)               # 90% (0-65536 = 0-100%)
# 
# DDE_EXHAUST_TEMP = PID((0x04, 0x1b), 2)
# DDE_AMBIENT_PRESSURE = PID((0x0c, 0x1c), 2)

TYPE_SINGLE = 0x0
TYPE_FIRST = 0x1
TYPE_CONSECUTIVE = 0x2
TYPE_FLOW = 0x3

FLOW_CONTINUE = 0x0
FLOW_WAIT = 0x1
FLOW_ABORT = 0x2


class TPFramer(object):
    class RXFrame(object):
        def __init__(self, msg):
            if (msg.arbitration_id & 0xf00) != 0x600:
                raise MessageError('not in the expected ID range')
            self.sender = msg.arbitration_id & 0xff
            self.recipient = msg.data[0]
            self.type = msg.data[1] >> 4
            self.length = None
            self.data = None
            self.sequence = None
            if self.type == TYPE_SINGLE:
                self.length = msg.data[1] & 0xf
                self.data = msg.data[2:]
            elif self.type == TYPE_FIRST:
                self.length = ((msg.data[1] & 0xf) << 8) + msg.data[2]
                self.data = msg.data[3:]
            elif self.type == TYPE_CONSECUTIVE:
                self.sequence = msg.data[1] & 0xf
                self.data = msg.data[2:]
            elif self.type == TYPE_FLOW:
                pass
            else:
                raise MessageError('not an expected TP frame')

    class TXFrame(object):
        def __init__(self, sender, recipient, data):
            self.type = TYPE_SINGLE if len(data) <= 6 else TYPE_FIRST
            self.sender = sender
            self.recipient = recipient
            self.data = data

        def next_message(self):
            if self.type == TYPE_SINGLE:
                msg = MSG_ISO_TP_single.message(sender=self.sender,
                                                recipient=self.recipient,
                                                data=self.data)
                self.type = None
                return msg

            if self.type == TYPE_FIRST:
                msg = MSG_ISO_TP_initial.message(sender=self.sender,
                                                 recipient=self.recipient,
                                                 data=self.data)
                self.data = self.data[5:]
                self.type = TYPE_CONSECUTIVE
                self.sequence = 1
                return msg

            if self.type == TYPE_CONSECUTIVE:
                msg = MSG_ISO_TP_consecutive.message(sender=self.sender,
                                                     recipient=self.recipient,
                                                     sequence=self.sequence,
                                                     data=self.data[:6])
                self.data = self.data[6:]
                self.sequence += 1
                if len(self.data) == 0:
                    self.type = None
                return msg

            return None

    def __init__(self, interface, module_id):
        self._interface = interface
        self._module_id = module_id
        self._inbound_data = None
        self._inbound_sender = None
        self._inbound_sequence = 0
        self._inbound_outstanding = 0
        self._outbound_frame = None

    def message_received(self, msg):
        try:
            frame = self.RXFrame(msg)
        except MessageError:
            return
        if frame.recipient != self._module_id:
            # not for us, ignore
            return

        # Got a single frame?
        if frame.type == TYPE_SINGLE:
            print('single')
            self._inbound_sender = frame.sender
            self._inbound_data = bytearray(frame.data[:frame.length])
            self._inbound_outstanding = 0

        # Got an initial frame?
        elif frame.type == TYPE_FIRST:
            print('first')
            self._inbound_sender = frame.sender
            if frame.length > len(frame.data):
                self._inbound_outstanding = frame.length - len(frame.data)
            else:
                self._inbound_outstanding = 0
            self._inbound_data = frame.data[0:frame.length]
            self._inbound_sequence = 1

            # send a flow control request for more
            self._interface.send(MSG_ISO_TP_flow_continue.message(sender=self._module_id,
                                                                  recipient=self._inbound_sender))

        # Got a continuation frame?
        elif ((self._inbound_data is not None) and
              (self._inbound_outstanding > 0) and
              (frame.type == TYPE_CONSECUTIVE) and
              (frame.sender == self._inbound_sender) and
              (frame.sequence == self._inbound_sequence)):
            print('cont')
            self._inbound_data += bytearray(frame.data[:self._inbound_outstanding])
            if self._inbound_outstanding <= len(frame.data):
                self._inbound_outstanding = 0
            else:
                self._inbound_outstanding -= len(frame.data)
            self._inbound_sequence = (self._inbound_sequence + 1) & 0xf

        # Got a flow-control frame
        # XXX should check the sender and respect more fields in this message
        elif ((frame.type == TYPE_FLOW) and
              (self._outbound_frame is not None)):
            # mostly disregard what the flow frame says and just spam the responses at 1ms intervals
            while True:
                msg = self._outbound_frame.next_message()
                if msg is None:
                    break
                self._interface.send(msg)
                time.sleep(0.001)
            self._outbound_frame = None

    def recv_frame(self):
        if ((self._inbound_data is None) or
            (self._inbound_outstanding != 0)):
            raise MessageError('no message')

        data = self._inbound_data
        self._inbound_data = None
        return self._inbound_sender, data

    def send_frame(self, recipient, data):
        self._outbound_frame = self.TXFrame(self._module_id, recipient, data)
        self._interface.send(self._outbound_frame.next_message())


class DDE(can.Listener):
    def __init__(self, interface, args):
        self._interface = interface
        self._tp_framer = TPFramer(interface, 0x12)
        self._setup = False
        if not args.no_periodic:
            self._dde_rpm_task = interface.send_periodic(MSG_DDE_rpm_tps.message(tps=0, rpm=(832 * 4)), 0.1)
            self._dde_coolant_task = interface.send_periodic(MSG_DDE_coolant.message(coolant_temp=27 + 48), 0.1)
            self._dde_brake_task = interface.send_periodic(MSG_DDE_torque_brake.message(False), 0.1)
        else:
            self._dde_rpm_task = None
            self._dde_coolant_task = None
            self._dde_brake_task = None
        self._interface.add_listener(self)

    def on_message_received(self, message):
        self._tp_framer.message_received(message)

        try:
            sender, data = self._tp_framer.recv_frame()
        except MessageError:
            return

        # compare payload with expected
        if sender != 0xf1:
            print(f'bad sender {sender:#x}')
        if self._setup:
            if (data != b'\x2c\x10'):
                print(f'reconfig but already set up')
        else:
            if data != b'\x2c\x10\x07\x72\x07\x6f\x04\x34\x07\x6d\x0e\xa6\x06\x07\x0a\x8d':
                print(f'expected setup but got {data.hex()}')
            else:
                self._setup = True

        # send dummy reply
        self._tp_framer.send_frame(sender, b'\x6c\x10\x00\x01\x10\x11\x20\x21\x30\x31\x40\x50\x60')

    def brake_on(self):
        if self._dde_brake_task is not None:
            self._dde_brake_task.modify_data(MSG_DDE_torque_brake.message(True))

    def brake_off(self):
        if self._dde_brake_task is not None:
            self._dde_brake_task.modify_data(MSG_DDE_torque_brake.message(False))


if __name__ == '__main__':
    import argparse
    import time
    from interface import Interface

    parser = argparse.ArgumentParser(description='E36 tail module DDE emulator')
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
    parser.add_argument('--no-periodic',
                        action='store_true',
                        help='disable periodic DDE message emulation')

    args = parser.parse_args()
    try:
        dde = DDE(Interface(args), args)

        print(f'DDE @ {args.interface_channel}')
        while True:
            time.sleep(1.0)
            dde.brake_on()
            time.sleep(1.0)
            dde.brake_off()
    except KeyboardInterrupt:
        pass
