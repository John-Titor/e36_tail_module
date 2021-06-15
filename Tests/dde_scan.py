#!/usr/bin/env python3

import time

from messages import *
from logger import Logger


# DDE scanner / repeater test
#
def do_dde_scan_test(interface, args):

    logger = Logger(None, args)
    logger.log('dde scanner test start')

    def expect_setup_request():
        """wait for a setup request"""
        msg = [
            MSG_BMW_parameter.long_with_initial_fields(0xf1, 0x12, 0x0e,
                                                       [0x2c,
                                                        0x10,
                                                        0x03,
                                                        0x85,
                                                        0x04]),
            MSG_BMW_parameter.long_with_continuation_fields(0xf1, 0x12, 0x21,
                                                            [0x1b,
                                                             0x07,
                                                             0x6f,
                                                             0x06,
                                                             0x6d,
                                                             0x0a]),
            MSG_BMW_parameter.long_with_continuation_fields(0xf1, 0x12, 0x22,
                                                            [0x8d,
                                                             0x10,
                                                             0x06,
                                                             0xff,
                                                             0xff,
                                                             0xff]),
        ]
        if interface.expect(msg[0]) is None:
            raise ModuleError('timed out waiting for setup request seq 0x10')
        interface.send(MSG_BMW_parameter.continuation_request(0x12, 0xf1))
        if interface.expect(msg[1]) is None:
            raise ModuleError('timed out waiting for setup request seq 0x21')
        if interface.expect(msg[2]) is None:
            raise ModuleError('timed out waiting for setup request seq 0x21')

    def expect_repeat_request():
        """wait for a repeat request"""
        msg = MSG_BMW_parameter.long_with_initial_fields(0xf1, 0x12, 0x02,
                                                         [0x2c,
                                                          0x10])
        if interface.expect(msg) is None:
            raise ModuleError('timed out waiting for repeat request')

    def send_response(offset):
        """send a canned response with predictable values"""
        interface.send(MSG_BMW_parameter.long_with_initial_fields(0x12,
                                                                  0xf1,
                                                                  0x0c,
                                                                  [0x6c,
                                                                   0x10,
                                                                   0x11 + offset,
                                                                   0x22 + offset,
                                                                   0x33 + offset]))

        if interface.expect(MSG_BMW_parameter.continuation_request(0xf1, 0x12)) is None:
            raise ModuleError('timeout waiting for reply-continue message')

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
        """get a parameter repeat message with expected values"""
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

    # wait for setup requests; ignore first, make sure there is a second
    expect_setup_request()
    expect_setup_request()
    logger.log('got setup request')

    # send response
    send_response(0)

    # wait for repeated version & validate values
    get_repeat(0x1122, 0x5566, 0x3344, 0x7788)
    logger.log('got echo')

    # wait for repeat request
    expect_repeat_request()
    logger.log('got repeat')

    # send response
    send_response(1)

    # wait for repeated version
    get_repeat(0x1223, 0x5667, 0x3445, 0x7889)
    logger.log('got echo 2')

    # ignore requests and wait for setup request again
    expect_setup_request()
    logger.log('got setup reset')

    # send message that looks like a 'real' scantool
    interface.send(MSG_BMW_parameter.short_with_fields(0xf1,
                                                       0x40,
                                                       [0x1a,
                                                        0x80]))

    # wait for a request - fail if we hear more than one
    count = 0
    while True:
        try:
            expect_setup_request()
            count += 1
        except ModuleError:
            break
        if count > 1:
            raise ModuleError('module did not silence after scantool sign-on')

    print('success')
