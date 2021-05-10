/*
 * Emulate the E90 CAS / JBE enough for diag tools to be happy.
 *
 * Most request messages are of the form
 *
 * id       = 0x6zz     0x600 + requester ID, usually 0xf1
 * dlc      = 8
 * data[0]  = xx        responder ID
 * data[1]  = nn        request length (1-6)
 * data[2..]            request bytes
 *
 * Responses are
 *
 * id       = 0x6xx     0x600 + repsonder ID
 * data[0]  = zz        requester ID
 * data[1]  = ss        sequence number (0x10, 0x21, 0x22...)
 * data[2..6]           message data, padded with 0xff
 *
 * Responses start by echoing the request bytes, then
 * a single-byte length value containing the number of
 * additional bytes to follow. If the response extends
 * beyond the first message, the responder will wait
 * for a message with the payload <xx 30 00 01 00 00 00 00>
 * before sending the remaining message bytes.
 */

#include <string.h>

#include <CAN1.h>

#include "timer.h"
#include "defs.h"

#define ID_JBE 0x00
#define ID_CAS 0x40
#define ID_ALL 0xef

static uint8_t req_buf[8];

static struct {
    const uint8_t   *bytes;
    uint8_t         residual;
    uint8_t         sequence;
} response_state;

static bool response_continue;


////////////////////////////////////////////////////////////////////////////////
// CAS_responses

// HARDWARE_REFERENZ_LESEN / read hardware/firmware versions
static const uint8_t cas_rsp_0x1a_0x80[] = {
    0x1a, 0x80,
    0x3C, 0x5A, 0x80, 0x00, 0x00, 0x09,
    0x38, 0x91, 0x16, 0xC4, 0x09, 0x06,
    0xA0, 0x53, 0x41, 0x20, 0x09, 0x05,
    0x20, 0x04, 0x00, 0x00, 0x00, 0x02,
    0x08, 0x01, 0x03, 0x03, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x06, 0x94,
    0x38, 0x06, 0x30, 0x31, 0x39, 0x30,
    0x30, 0x30, 0x34, 0x32, 0x4E, 0x37,
    0x44, 0x30, 0x30, 0x34, 0x32, 0x4E,
    0x37, 0x44, 0x46, 0x32, 0x32, 0x39,
    0x53, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
};


// VIN read
static const uint8_t cas_rsp_0x22_0x10_0x10[] = {
    0x22, 0x10, 0x10,
    0x14, 0x62, 0x10, 0x10, 0x57, 0x42,
    0x41, 0x50, 0x4E, 0x37, 0x33, 0x35,
    0x58, 0x39, 0x41, 0x32, 0x36, 0x36,
    0x33, 0x38, 0x36, 0xFF, 0xFF, 0xFF
};

// C_FA_LESEN / read VO block 0
static const uint8_t cas_rsp_0x22_0x3f_0x00[] = {
    0x22, 0x3f, 0x00,
    0x13, 0x62, 0x3F, 0x00, 0x02, 0x41,
    0x34, 0x19, 0x95, 0x94, 0x3F, 0xC2,
    0xE5, 0xD3, 0x41, 0x35, 0x54, 0xB2,
    0x3C, 0xF7, 0xFF, 0xFF, 0xFF, 0xFF
};

// C_FA_LESEN / read VO block 1
static const uint8_t cas_rsp_0x22_0x3f_0x01[] = {
    0x22, 0x3f, 0x01,
    0x13, 0x62, 0x3F, 0x01, 0x41, 0x04,
    0x10, 0x41, 0x04, 0x10, 0x41, 0x04,
    0x10, 0x41, 0x04, 0x10, 0x41, 0x04,
    0x10, 0x42, 0xFF, 0xFF, 0xFF, 0xFF
};

// C_FA_LESEN / read VO block 2
static const uint8_t cas_rsp_0x22_0x3f_0x02[] = {
    0x22, 0x3f, 0x02,
    0x13, 0x62, 0x3F, 0x02, 0x11, 0x8E,
    0x14, 0x90, 0x55, 0x2C, 0xFA, 0x51,
    0x65, 0x54, 0x65, 0x75, 0x21, 0x89,
    0x55, 0xD0, 0xFF, 0xFF, 0xFF, 0xFF
};

// C_FA_LESEN / read VO block 3
static const uint8_t cas_rsp_0x22_0x3f_0x03[] = {
    0x22, 0x3f, 0x03,
    0x13, 0x62, 0x3F, 0x03, 0x59, 0x15,
    0x58, 0x49, 0x36, 0x15, 0x41, 0x85,
    0x53, 0x61, 0x75, 0x99, 0x49, 0x53,
    0x21, 0x41, 0xFF, 0xFF, 0xFF, 0xFF
};

// C_FA_LESEN / read VO block 4
static const uint8_t cas_rsp_0x22_0x3f_0x04[] = {
    0x22, 0x3f, 0x04,
    0x13, 0x62, 0x3F, 0x04, 0x94, 0x00,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
};

// XXX unidentified
static const uint8_t cas_rsp_0x30_0x01_0x01[] = {
    0x30, 0x01, 0x01,
    0x43, 0x70, 0x01, 0x01, 0x83, 0xC8,
    0x00, 0x28, 0x97, 0x6C, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x6C, 0x01, 0x6C,
    0x6D, 0x6E, 0x6C, 0x6A, 0x00, 0x00,
    0x00, 0x01, 0xF0, 0x00, 0x02, 0x37,
    0x00, 0x4B, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x98, 0x9E,
    0x61, 0x00, 0xC1, 0x50, 0x06, 0x00,
    0x1B, 0x00, 0x00, 0x00, 0x00, 0x01,
    0x00, 0x00, 0x00, 0x45, 0x40, 0x21,
    0x8F, 0x36, 0x80, 0x00, 0x0D, 0xFF,
    0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF
};


////////////////////////////////////////////////////////////////////////////////
// JBE_responses

static const uint8_t jbe_rsp_0x1a_0x80[] = {
    0x1a, 0x80,
    0x1F, 0x5A, 0x80, 0x00, 0x00, 0x09,
    0x18, 0x75, 0x46, 0x03, 0x0A, 0x0D,
    0xD0, 0x4E, 0x52, 0x20, 0x05, 0x12,
    0x21, 0x09, 0x00, 0x1D, 0x88, 0x08,
    0x3F, 0x00, 0x03, 0x0A, 0x00, 0x00,
    0x00, 0x00, 0xFF, 0xFF, 0xFF, 0xFF
};


static const uint8_t *const CAS_responses[] = {
    &cas_rsp_0x1a_0x80[0],
    &cas_rsp_0x22_0x10_0x10[0],
    &cas_rsp_0x22_0x3f_0x00[0],
    &cas_rsp_0x22_0x3f_0x01[0],
    &cas_rsp_0x22_0x3f_0x02[0],
    &cas_rsp_0x22_0x3f_0x03[0],
    &cas_rsp_0x22_0x3f_0x04[0],
    &cas_rsp_0x30_0x01_0x01[0],
    NULL
};

static const uint8_t *const JBE_responses[] = {
    &jbe_rsp_0x1a_0x80[0],
    NULL
};

// Select a response from the indicated catalog
static bool
cas_jbe_select_response(const uint8_t * const *catalog)
{
    // First bytes of response echo the request, so just look for a matching
    // prefix given the request length
    while (*catalog != NULL) {
        if (!memcmp(*catalog, &req_buf[2], req_buf[1])) {
            // set response bytes
            response_state.bytes = *catalog;
            // response length is the byte after the request echo in the response
            response_state.residual = req_buf[1] + 1 + response_state.bytes[req_buf[1]];
            response_continue = FALSE;
            return TRUE;
        }
    }
    response_state.residual = 0;
    return FALSE;
}

// Send one message continuing the selected response
static void
cas_jbe_send_response(uint8_t respondent)
{
    uint8_t data[8];
    uint8_t ret;
    uint8_t index;

    REQUIRE(response_state.residual > 0);

    // response header
    data[0] = 0x1a;     // expected requester ID
    data[1] = response_state.sequence++;
    if (response_state.sequence == 0x11) {
        response_state.sequence = 0x21;
    }

    // response data bytes, plus padding
    index = 2;
    while ((index < 8) && (response_state.residual--)) {
        data[index++] = *response_state.bytes++;
    }
    while (index < 8) {
        data[index++] = 0xff;
    }
    do {
        ret = CAN1_SendFrameExt(0x600 | respondent, DATA_FRAME, 0x8, &data[0]);
    } while (ret == ERR_TXFULL);
}

// Handle sending periodic Terminal Status messages
static void
cas_jbe_send_terminal_status(void)
{
    static timer_t terminal_status_timer;

    if (!timer_registered(terminal_status_timer)) {
        timer_register(&terminal_status_timer);
        timer_reset(terminal_status_timer, 500);
    } 
    if (timer_expired(terminal_status_timer)) {
        uint8_t data[8];
        uint8_t ret;

        timer_reset(terminal_status_timer, 500);

        data[0] = 0xc5;
        data[1] = 0x40;
        data[2] = 0xff;
        data[3] = 0xff;
        data[4] = 0xff;

        do {
            ret = CAN1_SendFrameExt(0x130, DATA_FRAME, 5, &data[0]);
        } while (ret == ERR_TXFULL);
    }
}

// Handle receiving a new request
void
cas_jbe_recv(uint8_t *data)
{
    // ignore messages not addressed to at least one of CAS or JBE
    switch (data[0]) {
    case ID_JBE:
    case ID_CAS:
    case ID_ALL:
        break;
    default:
        return;
    }

    // Check for a flow-resume message.
    //
    // Note that we don't check who it's addressed to, since things
    // seem to assume that in the broadcast case only one module
    // is talking at all at a time, so we never offer data from
    // more than one respondent at once.
    //
    if ((data[1] == 0x30) &&
        (data[2] == 0x00) &&
        (data[3] == 0x01) &&
        (data[4] == 0x00) &&
        (data[5] == 0x00) &&
        (data[6] == 0x00) &&
        (data[7] == 0x00)) {

        // send the remainder of the message
        response_continue = TRUE;

        // sanity-check request length
    } else if (data[1] <= 6) {
        (void)memcpy(&req_buf, data, sizeof(req_buf));
        pt_reset(&pt_cas_jbe_emulator);
        response_state.residual = 0;
    }
}

void
cas_jbe_emulator(struct pt *pt)
{
    // Note that this code runs every time the PT is 
    // scheduled.
    cas_jbe_send_terminal_status();

    pt_begin(pt);

    // request targeted at CAS, or broadcast?
    if ((req_buf[0] == ID_CAS) ||
        (req_buf[0] == ID_ALL)) {

        // see if CAS handles this message
        if (cas_jbe_select_response(&CAS_responses[0])) {

            // it does, send reply
            cas_jbe_send_response(ID_CAS);

            // more reply bytes?
            if (response_state.residual) {
                pt_wait(pt, response_continue);
                while (response_state.residual) {
                    cas_jbe_send_response(ID_CAS);
                    pt_yield(pt);
                }
            }
        }
    }

    // request targeted at JBE, or broadcast?
    if ((req_buf[0] == ID_JBE) ||
        (req_buf[0] == ID_ALL)) {

        // see if JBE handles this message
        if (cas_jbe_select_response(&JBE_responses[0])) {

            // it does, send reply
            cas_jbe_send_response(ID_JBE);

            // more reply bytes?
            if (response_state.residual) {
                pt_wait(pt, response_continue);
                while (response_state.residual) {
                    cas_jbe_send_response(ID_JBE);
                    pt_yield(pt);
                }
            }
        }
    }

    pt_end(pt);
}
