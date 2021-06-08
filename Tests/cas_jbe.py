#!/usr/bin/env python3

import time

from messages import *
from logger import Logger


# CAS / JBE emulator test
#
def do_cas_jbe_test(interface, args):

    logger = Logger(None, args)

    def get_part_response(respondent):
        deadline = time.time() + 2
        while time.time() < deadline:
            msg = interface.recv(0.2)
            if msg is not None:
                try:
                    reply = MSG_BMW_parameter(msg)
                    if reply.sender == 0xf1:
                        # module trying to talk to DDE, ignore
                        continue
                    return reply
                except MessageError:
                    try:
                        logger.log_console(msg)
                    except KeyError:
                        pass
        return None

    def get_response(respondent, cmd):
        reply = get_part_response(respondent)
        if reply is None:
            raise ModuleError('timed out waiting for initial response')

        if reply.recipient != 0xf1:
            raise MessageError(f'message not addressed correctly: {reply}')
        if reply.sequence != 0x10:
            raise MessageError(f'message has wrong sequence: {reply}')
        if reply.length < len(cmd):
            raise MessageError(f'message length is too short: {reply}')

        cmd[0] |= 0x40
        for i in range(0, len(cmd)):
            if reply.data[i] != cmd[i]:
                raise MessageError(f'command echo mismatch: {reply.data[i]:02x} != {cmd[i]:02x}')

        residual = reply.length - len(cmd)
        if (residual > 0):
            interface.send(MSG_BMW_parameter.continuation_request(sender=0xf1,
                                                                  recipient=respondent))
            seq = 0x21

            while (residual > 0):
                reply = get_part_response(respondent)
                if reply is None:
                    raise ModuleError('timed out waiting for continued response')
                if reply.sequence != seq:
                    raise MessageError(f'wrong response sequence: {reply}')
                seq += 1
                residual -= 6

    # T15 on
    interface.set_power_t30_t15()

    # stall / monitor console for a couple of seconds
    get_part_response(0xfffffff)

    # send HARDWARE_REFERENZ_LESEN to the CAS
    cmd = [0x1a, 0x80]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # read the VIN from the CAS
    cmd = [0x22, 0x10, 0x10]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # expect a reply with the expected VIN

    # CA_FA_LESEN block 0
    cmd = [0x22, 0x3f, 0x00]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 1
    cmd = [0x22, 0x3f, 0x01]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 2
    cmd = [0x22, 0x3f, 0x02]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 3
    cmd = [0x22, 0x3f, 0x03]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 4
    cmd = [0x22, 0x3f, 0x04]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # ???
    cmd = [0x30, 0x01, 0x01]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # CA_FA_LESEN block 0 (repeated)
    cmd = [0x22, 0x3f, 0x00]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0x40,
                                                 cmd=cmd))
    get_response(0x40, cmd)

    # send HARDWARE_REFERENZ_LESEN to the broadcast address
    cmd = [0x1a, 0x80]
    interface.send(MSG_BMW_parameter.short_with_fields(sender=0xf1,
                                                 recipient=0xef,
                                                 cmd=cmd))
    get_response(0x40, cmd)
    get_response(0x00, cmd)

    logger.log('success')