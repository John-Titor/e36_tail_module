/*
 * Perform a periodic scan of BMW modules to fetch interesting
 * values, and re-broadcast them in messages that less
 * intelligent listeners can pick up.
 */

#include <string.h>

#include <CAN1.h>

#include "timer.h"
#include "defs.h"

bool    dde_oil_warning;
bool    dde_mil_state;

#define ISO_DDE_ID  0x12
#define ISO_TOOL_ID 0xf1

#define ISO_TIMEOUT 100

/*
 * Setup request that is sent.
 *
 * The reply buffer is transmitted literally in CAN messages starting
 * with ID 0x700.
 */
static const uint8_t dde_setup_req[] = {
    0x2c, 0x10, // read things
    // packed in 0x700
    0x07, 0x72, // air temperature at the HFM                       2B
    0x07, 0x6f, // air temperature after the charge cooler          2B
    0x04, 0x34, // exhaust gas temperature before particle filter   2B
    0x07, 0x6d, // boost pressure                                   2B
    // packed in 0x701
    0x0e, 0xa6, // current gear                                     1B
    0x06, 0x07, // transmission oil temperature                     1B
    0x0a, 0x8d, // oil pressure status                              1B
};

static const uint8_t dde_repeat_req[] = {
    0x2c, 0x10, // read things
};

#define DDE_SETUP_REQUEST_SIZE sizeof(dde_setup_req)
#define DDE_REPEAT_REQUEST_SIZE sizeof(dde_repeat_req)

// 11 bytes of data + 2 command status bytes
#define DDE_RESPONSE_SIZE 13

// we send raw from this buffer in groups of 8 starting at offset 2, 
// so make the buffer multiple-of-8 + 2 large
static uint8_t dde_rx_buffer[18];

// currently selected gear, used when "current gear" reported by trans is 0
static uint8_t selected_gear;

// display gear calculated using selected / current gear
uint8_t bmw_display_gear;

void
bmw_recv_gear(uint8_t gear_code)
{
    selected_gear = gear_code;
}

void
bmw_scanner(struct pt *pt)
{
    static timer_t bmw_timeout;
    static bool setup_sent;

    pt_begin(pt);
    timer_register(bmw_timeout);
    setup_sent = FALSE;

    for (;;) {
        uint8_t ret;
        
        // wait for the time to expire, then reset it
        // to minimise drift
        pt_wait(pt, timer_expired(bmw_timeout));
        timer_reset(bmw_timeout, CAN_BMW_INTERVAL);

        // prepare to receive DDE response
        (void)iso_tp_recv(DDE_RESPONSE_SIZE,
                          ISO_DDE_ID,
                          ISO_TIMEOUT,
                          &dde_rx_buffer[0]);

        if (!setup_sent) {
            (void)iso_tp_send(DDE_SETUP_REQUEST_SIZE,
                              ISO_DDE_ID,
                              ISO_TIMEOUT,
                              &dde_setup_req[0]);
        } else {
            (void)iso_tp_send(DDE_REPEAT_REQUEST_SIZE,
                              ISO_DDE_ID,
                              ISO_TIMEOUT,
                              &dde_repeat_req[0]);
        }

        // wait for receive to either complete or time out - transmit
        // must have succeeded if it completes successfully.
        for (;;) {
            // give up cycles first
            pt_yield(pt);

            // check for completion
            ret = iso_tp_recv_done();
            if (ret == ISO_TP_SUCCESS) {
                break;
            }
            if (ret != ISO_TP_BUSY) {
                // no good, reset and start again
                pt_abort(pt);
            }
        }

        // Echo the response buffer as a series of CAN frames with
        // IDs starting at 0x700.
        {
            static uint8_t sent;
            static uint32_t id;

            for (sent = 2, id = CAN_ID_BMW;
                 sent < DDE_RESPONSE_SIZE; 
                 sent += 8, id++) {
                can_send_blocking(id, &dde_rx_buffer[sent]);
                pt_yield(pt);
            }
        }

        // Compute the 'display' gear using 0e,a6 and the selected
        // gear reported in 0x1d2
        // selected gear: 120 = D, 180 = N, 210 = R, 225 = P 
        if (selected_gear == 120) {
            bmw_display_gear = dde_rx_buffer[10];
        } else {
            bmw_display_gear = selected_gear;
        }

        setup_sent = TRUE;
    }
    pt_end(pt);
}
