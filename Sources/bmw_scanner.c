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
#define ISO_EGS_ID  0x18
#define ISO_TOOL_ID 0xf1

#define ISO_TIMEOUT 100

static const uint8_t dde_setup_req[] = {
    0x2c, 0x10, // read things
    0x03, 0x85, // fuel temperature    2B
    0x04, 0x1b, // exhaust temperature 2B
    0x07, 0x6f, // intake temperature  2B
    0x06, 0x6d, // manifold pressure   2B
    0x0a, 0x8d, // oil pressure status 
    0x10, 0x06, // MIL
};

static const uint8_t egs_setup_req[] = {
    0x2c, 0x10, // read things
    // ...    
};

static const uint8_t repeat_req[] = {
    0x2c, 0x10, // read things
};


/*
 * Echo the contents of the DDE response as a custom frame.
 */
static bool
dde_echo_response(const iso_tp_req *rsp)
{

    if (rsp->len == 10) {
        // [0,1] Fuel temp in °C: (val / 100) - 55
        // [2,3] Exhaust temp in °C: ((val / 32) - 50) 
        // [4,5] Intake temp in °C: (val / 100) - 100
        // [6,7] Manifold pressure in mBar

        do {
            ret = CAN1_SendFrameExt(0x700, DATA_FRAME, 8, &buf[0]);
        } while (ret == ERR_TXFULL);

        // save these to report with other internal data
        dde_oil_warning = buf[8];
        dde_mil_state = buf[9];

        return true;
    } else {
        return false;
    }
}

/*
 * Echo the contents of the EGS response as a custom frame.
 */
static bool
egs_echo_response(const iso_tp_req *rsp)
{
    (void)rsp;
    return true;
}

void
bmw_scanner(struct pt *pt)
{
    static timer_t bmw_timeout;
    static uint8_t rx_buffer[16];   // XXX sizing
    static struct iso_tp_request tx_req;
    static struct iso_tp_request rx_req;
    static bool setup_sent = false;

    pt_begin(pt);
    timer_register(bmw_timeout);

    for (;;) {
        uint8_t ret;

        pt_wait(timer_expired(bmw_timeout));

        // do DDE query
        //
        (void)iso_tp_recv(10,
                          ISO_DDE_ID,
                          ISO_TOOL_ID,
                          ISO_TIMEOUT,
                          &rx_buffer);

        if (!setup_sent) {
            (void)iso_tp_send(sizeof(dde_setup_req),
                              ISO_TOOL_ID,
                              ISO_DDE_ID,
                              ISO_TIMEOUT,
                              &dde_setup_req[0]);
        } else {
            (void)iso_tp_send(sizeof(repeat_req),
                              ISO_TOOL_ID,
                              ISO_DDE_ID,
                              ISO_TIMEOUT,
                              &repeat_req[0]);
        }

        pt_wait((ret = iso_tp_send_done()) != ISO_TP_BUSY);
        if (ret == ISO_TP_SUCCESS) {
            pt_wait((ret == iso_tp_recv_done()) != ISO_TP_BUSY);
        }
        if ((ret != ISO_TP_SUCCESS) || !dde_echo_response(&rx_req)) {
            // no good, reset and start again
            pt_abort(pt);
        }
     
        // do EGS query
        //
        (void)iso_tp_recv(0,
                          ISO_EGS_ID,
                          ISO_TOOL_ID,
                          ISO_TIMEOUT,
                          &rx_buffer);

        if (!setup_sent) {
            (void)iso_tp_send(sizeof(egs_setup_req),
                              ISO_TOOL_ID,
                              ISO_EGS_ID,
                              ISO_TIMEOUT,
                              &egs_setup_req[0]);
        } else {
            (void)iso_tp_send(sizeof(repeat_req),
                              ISO_TOOL_ID,
                              ISO_EGS_ID,
                              ISO_TIMEOUT,
                              &repeat_req[0]);
        }

        pt_wait((ret = iso_tp_send_done()) != ISO_TP_BUSY);
        if (ret == ISO_TP_SUCCESS) {
            pt_wait((ret == iso_tp_recv_done()) != ISO_TP_BUSY);
        }
        if ((ret != ISO_TP_SUCCESS) || egs_echo_response(&rx_req)) {
            // no good, reset and start again
            pt_abort(pt);
        }

        setup_sent = true;

        // wait for the next poll cycle
        timer_reset(bmw_timeout, CAN_BMW_INTERVAL);
    }
    pt_end(pt);
}
