#!/usr/bin/env python3

import curses

from messages import *

# message IDs
CONSOLE_ID = 0x1ffffffe


class Logger(object):
    def __init__(self, win, args):
        self._verbose = args.verbose
        self._win = win
        if self._win is not None:
            self._win.addstr(0, 0, 'initializing...\n')
            self._win.idlok(True)
            self._win.scrollok(True)
            self._win.refresh()
        self._cons_buf = ''

    def log_can(self, msg):
        if self._verbose:
            self.log(f'CAN: {msg}')

    def log_console(self, msg):
        if msg.arbitration_id != CONSOLE_ID:
            raise KeyError
        for idx in range(0, msg.dlc):
            if msg.data[idx] == 0:
                self.log(f'CONS: {self._cons_buf}', curses.A_BOLD)
                self._cons_buf = ''
            else:
                self._cons_buf += chr(msg.data[idx])

    def log(self, msg, attr=curses.A_DIM):
        if self._win is not None:
            self._win.addstr(f'{msg}\n', attr)
            self._win.refresh()
        else:
            print(f'{msg}')
