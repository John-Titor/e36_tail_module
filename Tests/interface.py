#
# PythonCAN interface shim.
#
# Assumes we are talking to an AnaGate CAN X-something
# with digital output 1 wired to control power on the
# module.
#

import time
import can


class ModuleError(Exception):
    pass


class Interface(object):
    def __init__(self, args):
        self._power_on = False
        self.bus = can.ThreadSafeBus(interface='anagate',
                                     channel=args.interface_channel,
                                     bitrate=args.bitrate * 1000)
        self.notifier = can.Notifier(self.bus, [])

    def add_listener(self, listener):
        self.notifier.add_listener(listener)

    def send(self, message):
        return self.bus.send(message)

    def send_periodic(self, message, interval):
        return self.bus.send_periodic(message, interval)

    def recv(self, timeout):
        """
        wait for a message
        """
        now = time.time()
        deadline = now + timeout
        while time.time() < deadline:
            message = self.bus.recv(timeout=deadline - time.time())
            if message is not None:
                return message

    def set_power_on(self):
        self.bus.connection.set_analog_out(1, 12000)

    def set_power_off(self):
        self.bus.connection.set_analog_out(1, 0)

    def __del__(self):
        try:
            self.notifier.stop()
        except AttributeError:
            pass
