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

                # verify that it's a full setup request
                if len(req) == 14:
                    if ((req[0] != 0x2c) or
                        (req[1] != 0x10) or
                        (req[2] != 0x03) or
                        (req[3] != 0x85) or
                        (req[4] != 0x04) or
                        (req[5] != 0x1b) or
                        (req[6] != 0x07) or
                        (req[7] != 0x6f) or
                        (req[8] != 0x06) or
                        (req[9] != 0x6d) or
                        (req[10] != 0x0a) or
                        (req[11] != 0x8d) or
                        (req[12] != 0x10) or
                        (req[13] != 0x06)):
                        raise MessageError(f'malformed full request {req}')
                else if len(req) == 2:
                    if ((req[0] != 0x2c) or
                        (req[1] != 0x10)):
                        raise MessageError(f'malformed resume request {req}')
                else:
                    raise MessageError(f'malformed request {req}')
                return len(req)

        raise ModuleError('timeout waiting for request')

    def send_response(offset):
        interface.send(MSG_BMW_parameter.long_with_initial_fields(0x12,
                                                                  0xf1,
                                                                  0x0c,
                                                                  [0x6c,
                                                                   0x10,
                                                                   0x11 + offset,
                                                                   0x22 + offset,
                                                                   0x33 + offset]))
        interface.send(MSG_BMW_parameter.long_with_continuation_fields(0x12,
                                                                       0xf1,
                                                                       0x21,
                                                                       [0x44 + offset,
                                                                        0x55 + offset,
                                                                        0x66 + offset,
                                                                        0x77 + offset,
                                                                        0x88 + offset,
                                                                        0x99 + offset]))
        interface.send(MSG_BMW_parameter.long_with_continuation_fields(0x12,
                                                                       0xf1,
                                                                       0x22,
                                                                       [0x00 + offset,
                                                                        0xff,
                                                                        0xff,
                                                                        0xff,
                                                                        0xff,
                                                                        0xff]))

    def get_repeat(expected_ft, expected_iat, expected_egt, expected_map):
        """get a parameter repeat message"""
        deadline = time.time() + 1.0
        while time.time() < deadline:
            msg = interface.recv(0.1)
            try:
                rep = MSG_status_dde(msg)
            except MessageError:
                continue

            if ((expected_ft != rep.fuel_temp) or
                (expected_iat != rep.intake_temp) or
                (expected_egt != rep.exhaust_temp) or
                (expected_map != rep.manifold_pressure)):
                raise MessageError(f'unexpected returned results: {rep}')
            return

        raise ModuleError('timeout waiting for repeat')

    # wait for setup request
    req = get_request()

    # ignore it

    # wait for setup request
    reqlen = get_request()

    # verify that it's a full setup request
    if reqlen != 14:
        raise MessageError(f'expected 14 bytes of request, got {reqlen}')

    # send response
    send_response(0)

    # wait for repeated version & validate values
    get_repeat(0x1122, 0x3344, 0x5566, 0x7788)

    # wait for repeat request
    reqlen = get_request()

    # verify that it's a repeat request
    if reqlen != 2:
        raise MessageError(f'expected 2 bytes of repeat request, got {reqlen}')

    # send response
    send_response(1)

    # wait for repeated version
    get_repeat(0x1223, 0x3445, 0x5667, 0x7889)

    # ignore requests and wait for setup request again
    deadline = time.time() + 2.0
    while True:
        reqlen = get_request()
        if reqlen == 14:
            break
        if time.time() > deadline:
            raise ModuleError(f'module did not re-send setup request')

    # send message that looks like a 'real' scantool
    interface.send(MSG_BMW_parameter.short_with_fields(0xf1,
                                                       0x40,
                                                       [0x02,
                                                        0x1a,
                                                        0x80,
                                                        0x00,
                                                        0x00,
                                                        0x00,
                                                        0x00]))

    # wait for a request - fail if we hear more than one
    try:
        get_request()
        raise RuntimeError('module did not silence after scantool signed on')
    except ModuleError:
        pass

    print('success')

