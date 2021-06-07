#!/usr/bin/env python3

import time

from messages import *
from logger import Logger


# DDE scanner / repeater test
#
def do_dde_scan(interface, args):

    logger = Logger(None, args)

    def get_request():
        """get a parameter request"""
        deadline = time.time() + 1.0
        request = []
        expected_sequence = 0x10
        expected_length = 0
        while time.time() < deadline:
            msg = interface.recv(0.1)
            try:
                req = MSG_BMW_parameter(msg, 0xf1)
            except MessageError:
                continue

            if req.sequence != expected_sequence:
                raise MessageError(f'unexpected sequence {req.sequence}')

            if expected_sequence == 0x10:
                expected_length = req.length
            request += req.data

            if len(request) >= expected_length:
                return request

        raise ModuleError('timeout waiting for request')


    # wait for setup request

    # ignore it

    # wait for setup request

    # send response

    # wait for repeated version

    # wait for repeat request

    # send response

    # wait for repeated version

    # ignore requests and wait for setup request again

    # send message that looks like a 'real' scantool

    # wait for a request - fail if we hear more than one
