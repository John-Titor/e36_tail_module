#!/usr/bin/env python3

import time
from messages import MSG_mjs_power, MSG_ack
from PCANBasic import *


class CANInterface(object):
    def __init__(self, args):
        speed_table = {
            1000: PCAN_BAUD_1M,
            800: PCAN_BAUD_800K,
            500: PCAN_BAUD_500K,
            250: PCAN_BAUD_250K,
            125: PCAN_BAUD_125K,
        }
        try:
            speed = speed_table[args.can_speed]
        except KeyError:
            raise RuntimeError(f'Requested CAN speed {args.can_speed} not supported')

        self._verbose = args.verbose
        self._pcan = PCANBasic()
        self._channel = PCAN_USBBUS1
        result = self._pcan.Initialize(self._channel, speed)
        if result != PCAN_ERROR_OK:
            raise RuntimeError(f'PCAN init failed: {self._pcan.GetErrorText(result)}')
        self._pcan.Reset(self._channel)

    def send(self, message):
        """send the message"""
        self._trace(f'CAN TX: {message}')
        self._pcan.Write(self._channel, message.raw)

    def recv(self, timeout=2):
        """
        wait for a message

        Poll hard for the first 100ms, then fall back to only checking once every 10ms.
        """
        now = time.time()
        deadline = now + timeout
        fastpoll = now + 0.1
        while True:
            (status, msg, _) = self._pcan.Read(self._channel)
            if status == PCAN_ERROR_OK:
                if msg.ID in RECEIVE_FILTER:
                    self._trace(f'CAN RX: {msg}')
                    return msg
            elif status != PCAN_ERROR_QRCVEMPTY:
                raise RuntimeError(f'PCAN read failed: {self._pcan.GetErrorText(status)}')
            now = time.time()
            if now > deadline:
                return None
            if now > fastpoll:
                time.sleep(0.01)

    def set_power_off(self):
        self.send(MSG_module_power(False, False))

    def set_power_t30(self):
        self.send(MSG_module_power(True, False))

    def set_power_t30_t15(self):
        self.send(MSG_module_power(True, True))

    def detect(self):
        """
        Power on the module and listen for it to sign on.
        Send it a select to keep it in the bootloader for a while.
        Returns the ID of the detected module.
        """
        self.set_power_off()
        time.sleep(0.25)
        self._drain()
        self.set_power_t30()
        while True:
            rsp = self.recv(5)
            if rsp is None:
                raise ModuleError('no power-on message from module')
            try:
                signon = MSG_ack(rsp)
                break
            except MessageError as e:
                raise ModuleError(f'unexpected power-on message from module: {rsp}')
        self.send(MSG_select(signon.module_id))
        rsp = self.recv()
        if rsp is None:
            raise ModuleError('no select response from module')
        try:
            signon = MSG_selected(rsp)
        except MessageError as e:
            raise ModuleError(f'unexpected select response from module : {rsp}')
        return signon.module_id
