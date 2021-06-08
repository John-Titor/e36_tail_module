/*
 * Perform a periodic scan of the DDE to fetch interesting
 * values, and re-broadcast them in messages that less
 * intelligent listeners can pick up.
 */

#include <string.h>

#include <CAN1.h>

#include "timer.h"
#include "defs.h"

static uint8_t  buf[64];
static uint8_t  buflen;
static uint8_t  bufidx;

dde_state_t     dde_state;
bool            dde_state_updated;

static void
dde_send(const uint8_t *data)
{
    uint8_t ret;

    do {
        ret = CAN1_SendFrame(1, 0x6f1, DATA_FRAME, 0x08, (uint8_t *)data);
    } while (ret == ERR_TXFULL);
}

static void
dde_send_initial_req()
{
    static const uint8_t req[] = {
        0x12,       // DDE
        0x10,       // first message
        0x00,       // filled with length later
        0x2c, 0x10, // read things
        0x03, 0x85, // fuel temperature
        0x04, 0x1b, // exhaust temperature
        0x07, 0x6f, // intake temperature
        0x06, 0x6d, // manifold pressure
        0x0a, 0x8d, // oil pressure status
        0x10, 0x06, // MIL
    };

    // copy request
    (void)memcpy(buf, req, sizeof(req));
    buflen = sizeof(req);
    buf[2] = sizeof(req) - 3;

    // send request
    dde_send(&buf[0]);

    // account for sent portion
    if (buflen <= 8) {
        bufidx = 0;
        buflen = 0;
    } else {
        bufidx = 8;
    }
}

static void
dde_parse_rsp()
{
    if (buflen == sizeof(dde_state)) {
        (void)memcpy(&dde_state, &buf[0], sizeof(dde_state));
    }
    dde_state_updated = TRUE;
}

static void
dde_send_repeat_req()
{
    static const uint8_t req[] = { 0x12, 0x10, 0x02, 0x2c, 0x10, 0x00, 0x00, 0x00 };

    dde_send(&req[0]);
}

static void
dde_send_req_continue()
{
    static const uint8_t req_continue[] = {
        0x12, 0x30, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00
    };

    dde_send(&req_continue[0]);
}

static void
dde_send_complete()
{
    uint8_t seq = 0x21;
    bufidx = 6;

    while (bufidx < buflen) {
        uint8_t i;
        uint8_t data[8];

        data[0] = 0x12;
        data[1] = seq++;
        for (i = 2; i < 8; i++) {
            if (bufidx < buflen) {
                data[i] = buf[bufidx++];
            } else {
                data[i] = 0xff;
           }
        }

        dde_send(&data[0]);
    }
    buflen = 0;
    bufidx = 0;
}

void
dde_recv(uint8_t *data)
{
    // DDE asking for the rest of our request?
    //
    if ((data[0] == 0xf1) &&
        (data[1] == 0x30) &&
        (data[2] == 0x00) &&
        (data[3] == 0x01)) {

        dde_send_complete();
        return;
    }

    // DDE sending the first part of a response?
    //
    if ((data[0] == 0xf1) &&
        (data[1] == 0x10) &&
        (data[3] == 0x6c) &&
        (data[4] == 0x10)) {

        // copy initial response bytes
        buflen = data[2];
        for (bufidx = 0; (bufidx < 3) && (bufidx < buflen); bufidx++) {
            buf[bufidx] = data[5 + bufidx];
        }

        // more response bytes needed?
        if (bufidx < buflen) {
            dde_send_req_continue();
        }
        return;
    }

    // DDE sending more data?
    //
    if ((data[0] == 0xf1) &&
        (data[1] > 0x20) &&
        (bufidx < buflen)) {

        uint8_t ofs;
        for (ofs = 2; (ofs < 8) && (bufidx < buflen); ofs++) {
            buf[bufidx++] = data[ofs];
        }
        return;
    }
}

void
dde_scanner(struct pt *pt)
{
    static timer_t dde_timeout;

    pt_begin(pt);
    timer_register(dde_timeout);

    // Send initial request
    dde_send_initial_req();

    // loop
    for (;;) {
        // wait for reply
        timer_reset(dde_timeout, 100);
        pt_wait(pt, timer_expired(dde_timeout) || ((buflen > 0) && (bufidx == buflen)));
        if (timer_expired(dde_timeout)) {
            pt_reset(pt);
            return;
        }

        // process response buffer
        dde_parse_rsp();

        // wait 100ms
        pt_delay(pt, dde_timeout, 100);

        // Send repeat request
        dde_send_repeat_req();
    }

    pt_end(pt);
}
