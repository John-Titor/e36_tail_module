#!/usr/bin/env python3

import can
import time
from messages import MSG_mjs_power, MSG_ack


class CANInterface(object):
    def __init__(self, args):
        self._verbose = args.verbose
        # bootloader always signs on at 125kbps
        self._interface_type = args.interface_type
        self._interface = args.interface
        self._reinit(125000)
        self._detect(args.T15_at_start)

        # get a new interface at the runtime bitrate
        self._reinit(args.can_speed)

    def _reinit(self, bitrate):
        self._bus = can.interface.Bus(bustype=self._interface_type,
                                      channel=self._interface,
                                      bitrate=bitrate,
                                      sleep_after_open=0.2)

    def _detect(self, with_t15=False):
        """
        Power on the module and listen for it to sign on.
        Returns the ID of the detected module.
        """
        self.set_power_off()
        while self.recv(0.25) is not None:
            # drain buffered messages
            pass
        if with_t15:
            self.set_power_t30_t15()
        else:
            self.set_power_t30()
        while True:
            rsp = self.recv(2)
            if rsp is None:
                raise ModuleError('no power-on message from module')
            try:
                signon = MSG_ack(rsp)
                break
            except MessageError as e:
                raise ModuleError(f'unexpected power-on message '
                                  'from module: {rsp}')
        return signon.module_id

    def send(self, message):
        """send the message"""
        self._bus.send(message.raw, 1)
        if self._verbose:
            print(f'CAN SEND: {message}')

    def recv(self, timeout=2):
        """
        wait for a message

        Note the can module will barf if a bad message is received, so we need
        to catch this and retry.
        """
        deadline = time.time() + timeout
        while True:
            wait_time = deadline - time.time()
            if wait_time <= 0:
                return None
            try:
                message = self._bus.recv(wait_time)
                if self._verbose and message is not None:
                    print(f'CAN RECV: {message}')
                return message
            except Exception:
                pass

    def expect(self, expect_msg, timeout=2):
        """expect to receive a specific message within the timeout"""
        deadline = time.time() + timeout
        while True:
            wait_time = deadline - time.time()
            if wait_time <= 0:
                return None
            msg = self.recv(0.1)
            if msg is not None:
                match = ((msg.arbitration_id == expect_msg.raw.arbitration_id) and
                         (msg.is_extended_id == expect_msg.raw.is_extended_id) and
                         (msg.dlc == expect_msg.raw.dlc))
                if match:
                    for idx in range(0, msg.dlc):
                        if expect_msg.raw.data[idx] is not None:
                            if msg.data[idx] != expect_msg.raw.data[idx]:
                                match = False
                if match:
                    return msg

    def set_power_off(self):
        self.send(MSG_mjs_power.with_fields(False, False))

    def set_power_t30(self):
        self.send(MSG_mjs_power.with_fields(True, False))

    def set_power_t30_t15(self):
        self.send(MSG_mjs_power.with_fields(True, True))
