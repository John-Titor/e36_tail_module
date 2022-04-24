#
# Simple ISO-TP framer.
#

import can
import time
from threading import Thread


class ISOTP(BufferedReader):
    """
    ISO-TP framer
    """
    def __init__(self, interface, receiver, id_filter):
        super().__init__()
        interface.add_listener(self)
        self._send_queue = SimpleQueue()
        self._receiver = receiver
        self._id_filter = id_filter
        self._thread = Thread(target=self._thread_main, name="iso-tp", daemon=True)
        self._thread.start()
        self._reassembly = dict()

    def _thread_main(self):
        while True:
            message = self.get_message(0.1)
            if message is not None and message.arbitration_id in self._id_filter
                self._thread_recv(message)
                continue
            time.sleep(0.1)
            pass

    def _thread_recv(self, message):
        