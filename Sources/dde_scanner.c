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

bool    dde_oil_warning;
bool    dde_mil_state;

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
    bufidx = 8;
}

static bool
dde_echo_response()
{
    if ((buflen > 0) && (bufidx == buflen)) {

        // reflect the query response
        uint8_t data[8];
        uint8_t ret;

        // Fuel temp in °C: (val / 100) - 55
        data[0] = buf[0];
        data[1] = buf[1];

        // Air temp in °C: (val / 100) - 100
        data[2] = buf[4];
        data[3] = buf[5];

        // Exhaust temp in °C: ((val / 32) - 50) 
        data[4] = buf[2];
        data[5] = buf[3];

        // Manifold pressure in mBar
        data[6] = buf[6];
        data[7] = buf[7];

        do {
            ret = CAN1_SendFrameExt(0x700, DATA_FRAME, 8, &data[0]);
        } while (ret == ERR_TXFULL);

        // save these to report with other internal data
        dde_oil_warning = buf[8];
        dde_mil_state = buf[9];

        buflen = bufidx = 0;
        return TRUE;
    }
    return FALSE;
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

    // wait for request to be sent or timeout
    timer_reset(dde_timeout, CAN_DDE_TIMEOUT);
    pt_wait(pt, (buflen == 0) || timer_expired(dde_timeout));

    if (buflen != 0) {
        // timed out, reset thread and try again
        pt_reset(pt);
        return;
    }

    // reset timout for reply
    timer_reset(dde_timeout, CAN_DDE_TIMEOUT);

    // loop echoing reply & sending repeat request
    for (;;) {
        if (dde_echo_response() == TRUE) {
            // wait 100ms
            pt_delay(pt, dde_timeout, CAN_REPORT_INTERVAL_STATE);

            // Send repeat request
            dde_send_repeat_req();

            // wait for reply
            timer_reset(dde_timeout, CAN_DDE_TIMEOUT);
        } 
        else if (timer_expired(dde_timeout)) {
            pt_reset(pt);
            return;
        } 
        else {
            pt_yield(pt);
        }
    }
    pt_end(pt);
}
