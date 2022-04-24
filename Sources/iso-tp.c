/* 
 * ISO-TP over CAN encapsulation.
 *
 * https://en.wikipedia.org/wiki/ISO_15765-2
 *
 * Supports a single frame in each direction at a time.
 */

#include <CAN1.h>

#include "defs.h"
#include "timer.h"

enum {
    TP_SINGLE_FRAME         = 0,
    TP_FIRST_FRAME          = 1,
    TP_CONSECUTIVE_FRAME    = 2,
    TP_FLOW_CONTROL_FRAME   = 3
};

typedef struct {
    uint8_t     recipient;
    uint8_t     _res:4;
    uint8_t     type:4;
}       tp_header_t;

typedef struct {
    uint8_t     recipient;
    uint8_t     len:4;
    uint8_t     type:4;
    uint8_t     data[6];
}       tp_single_t;

typedef struct {
    uint8_t     recipient;
    uint8_t     len_hi:4;
    uint8_t     type:4;
    uint8_t     len_lo;
    uint8_t     data[5];
}       tp_first_t;

typedef struct {
    uint8_t     recipient;
    uint8_t     index:4;
    uint8_t     type:4;
    uint8_t     data[6];
}       tp_consecutive_t;

typedef struct {
    uint8_t     recipient;
    uint8_t     flag:4;
    uint8_t     type:4;
    uint8_t     block_size;
    uint8_t     st;
    uint8_t     _res[4];
}       tp_flow_t;

enum {
    TP_FLOW_CONTINUE    = 0,
    TP_FLOW_WAIT        = 1,
    TP_FLOW_ABORT       = 2
};

typedef union {
    tp_header_t         header;
    tp_single_t         single;
    tp_first_t          first;
    tp_consecutive_t    consecutive;
    tp_flow_t           flow;
    uint8_t             raw[8];
} tp_frame_t;

static struct {
    // parameters
    uint8_t         recipient;
    uint8_t         resid;
    uint8_t         sequence;
    timer_t         timeout;
    const uint8_t   *buf;

    // internal state
    uint8_t         window_resid;
    uint8_t         interval_ms;
    timer_t         interval;
} tp_tx;

static struct {
    // parameters
    uint8_t         sender;
    uint8_t         resid;
    uint8_t         *buf;
    timer_t         timeout;

    // internal state
    uint8_t         sequence;
} tp_rx;

// Set up a message to be sent in one or more ISO-TP frames
//
uint8_t
iso_tp_send(uint8_t len,
            uint8_t recipient,
            uint16_t timeout_ms,
            const uint8_t *buf)
{
    tp_frame_t  tf;
    uint8_t     i;
    uint8_t     ret;

    // can't start another transmission if still sending
    ret = iso_tp_send_done();
    if (ret == ISO_TP_BUSY) {
        return ret;
    }

    // if the message fits a short frame, pack entire message
    if (len <= sizeof(tf.single.data)) {

        // pack a SINGLE_FRAME message
        tf.single.recipient = recipient;
        tf.single.type = TP_SINGLE_FRAME;
        tf.single.len = len;
        for (i = 0; i < sizeof(tf.single.data); i++) {
            tf.single.data[i] = (i < len) ? buf[i] : 0;
        }

        // set up the rest of the request so that we can report 
        // immediate completion
        tp_tx.resid = 0;
        tp_tx.sequence = 0;
        timer_reset(tp_tx.timeout, 0);
        tp_tx.buf = NULL;
    } 

    // otherwise pack a first frame and set up to continue
    else {

        // pack a FIRST_FRAME message
        tf.first.recipient = recipient;
        tf.first.type = TP_FIRST_FRAME;
        tf.first.len_hi = 0;
        tf.first.len_lo = len;
        for (i = 0; i < sizeof(tf.first.data); i++) {
            tf.first.data[i] = buf[i];
        }

        // set up the rest of the request so that we can continue
        // it once a flow control message arrives
        tp_tx.recipient = recipient;
        tp_tx.resid = len - sizeof(tf.first.data);
        tp_tx.sequence = 1;
        timer_register(tp_tx.timeout);
        timer_reset(tp_tx.timeout, timeout_ms);
        tp_tx.buf = buf + sizeof(tf.first.data);

        tp_tx.window_resid = 0;
        tp_tx.interval_ms = 0;
    }

    // send first/initial frame
    can_send_blocking(0x600 + ISO_TP_NODE_ID, &(tf.raw[0]));
    return ISO_TP_SUCCESS;
}

// Possibly continue message transmission by sending another
// ISO-TP consecutive frame.
//
static void
iso_tp_tx_send_next(void)
{
    tp_frame_t  tf;
    uint8_t     i;

    if ((iso_tp_send_done() == ISO_TP_BUSY) &&
        timer_expired(tp_tx.interval) &&
        (tp_tx.window_resid > 0)) {

        tf.consecutive.recipient = tp_tx.recipient;
        tf.consecutive.type = TP_CONSECUTIVE_FRAME;
        tf.consecutive.index = tp_tx.sequence;
        tp_tx.sequence = (tp_tx.sequence + 1) & 0x0f;

        for (i = 0; i < sizeof(tf.consecutive.data); i++) {
            if (tp_tx.resid > 0) {
                tf.consecutive.data[i] = *tp_tx.buf++;
                tp_tx.resid--;    
            } else {
                tf.consecutive.data[i] = 0xff;
            }
        }

        // send consecutive frame
        can_send_blocking(0x600 + ISO_TP_NODE_ID, &(tf.raw[0]));
        tp_tx.window_resid--;
        timer_reset(tp_tx.interval, tp_tx.interval_ms);
    }
}

// Test whether transmission of the previously-started message
// is still ongoing.
//
uint8_t
iso_tp_send_done()
{
    // no outstanding data? must be success
    if (tp_tx.resid == 0) {
        return ISO_TP_SUCCESS;
    }

    // outstanding data and not timed out? must be busy
    if (!timer_expired(tp_tx.timeout)) {
        return ISO_TP_BUSY;
    }

    // outstanding data but timed out? clear resid and
    // return failure
    tp_tx.resid = 0;
    return ISO_TP_TIMEOUT;
}

// Set up to expect an incoming ISO-TP encapsulated message.
//
uint8_t
iso_tp_recv(uint8_t len,
            uint8_t sender,
            uint16_t timeout_ms,
            uint8_t *buf)
{
    uint8_t ret = iso_tp_recv_done();
    if (ret == ISO_TP_BUSY) {
        return ret;
    }

    tp_rx.sender = sender;
    tp_rx.resid = len;
    tp_rx.buf = buf;
    timer_register(tp_rx.timeout);
    timer_reset(tp_rx.timeout, timeout_ms);
}

// Test whether reception of the expected message is still
// ongoing.
//
bool
iso_tp_recv_done()
{
    // no outstanding data? must be success
    if (tp_rx.resid == 0) {
        return ISO_TP_SUCCESS;
    }

    // outstanding data and not timed out? must be busy
    if (!timer_expired(tp_rx.timeout)) {
        return ISO_TP_BUSY;
    }

    // outstanding data but timed out? clear resid and
    // return failure
    tp_tx.resid = 0;
    return ISO_TP_TIMEOUT;
}

static void
iso_tp_rx_flow(uint8_t sender, const tp_flow_t *tf)
{
    if ((iso_tp_send_done() == ISO_TP_BUSY) &&
        (sender == tp_tx.recipient) &&
        (tp_tx.window_resid == 0) &&
        (tf->flag == TP_FLOW_CONTINUE)) {

        // set up sequenced transmission of the next block of frames
        tp_tx.window_resid = tf->block_size ? tf->block_size : 0xff;
        tp_tx.interval_ms = tf->st;   // TODO <FLOW_ST>
        timer_register(tp_tx.interval);
        timer_reset(tp_tx.interval, 0);
        iso_tp_tx_send_next();
    }
}

static void
iso_tp_rx_single(uint8_t sender, const tp_single_t *ts)
{
    uint8_t i;

    if ((iso_tp_recv_done() == ISO_TP_BUSY) &&
        (sender == tp_rx.sender) &&
        (ts->len == tp_rx.resid)) {

        for (i = 0; i < tp_rx.resid; i++) {
            tp_rx.buf[i] = ts->data[i];
        }
        tp_rx.resid = 0;
    }
}

static void
iso_tp_rx_first(uint8_t sender, const tp_first_t *tf)
{
    tp_frame_t ff;
    uint8_t i;

    if ((iso_tp_recv_done() == ISO_TP_BUSY) &&
        (sender == tp_rx.sender) &&
        (tf->len_hi == 0) &&
        (tf->len_lo == tp_rx.resid)) {

        for (i = 0;
             tp_rx.resid && (i < sizeof(tf->data));
             i++, tp_rx.resid--, tp_rx.buf++) {

            *tp_rx.buf = tf->data[i];
        }
        tp_rx.sequence = 1;

        ff.flow.recipient = tp_rx.sender;
        ff.flow.type = TP_FLOW_CONTROL_FRAME;
        ff.flow.flag = TP_FLOW_CONTINUE;
        ff.flow.block_size = 0x00;  // send all remaining
        ff.flow.st = 1;             // 1ms pacing
        ff.flow._res[0] = 0;
        ff.flow._res[1] = 0;
        ff.flow._res[2] = 0;
        ff.flow._res[3] = 0;

        // send flow control message asking for more
        can_send_blocking(0x600 + ISO_TP_NODE_ID, &(ff.raw[0]));
    }
}

static void
iso_tp_rx_consecutive(uint8_t sender, const tp_consecutive_t *tc)
{
    uint8_t i;

    if ((iso_tp_recv_done() == ISO_TP_BUSY) &&
        (sender == tp_rx.sender) &&
        (tc->index == tp_rx.sequence)) {

        for (i = 0;
             tp_rx.resid && (i < sizeof(tc->data));
             i++, tp_rx.resid--, tp_rx.buf++) {

            *tp_rx.buf = tc->data[i];
        }

        tp_rx.sequence = (tp_rx.sequence + 1) & 0x0f;
    }

}

// Handle a presumed ISO-TP frame, called from the CAN listener
// thread.
//
void
iso_tp_can_rx(uint8_t sender, uint8_t *data)
{
    tp_frame_t *tf = (tp_frame_t *)data;
    uint8_t sender_id = sender & 0xff;

    // ignore frames not intended for this node
    if (tf->header.recipient != ISO_TP_NODE_ID) {
        return;
    }

    // is this a flow-control message to the current sender, and
    // are they waiting for one?
    if (tf->header.type == TP_FLOW_CONTROL_FRAME) {
        iso_tp_rx_flow(sender_id, &tf->flow);
        return;
    }

    // is this a single frame aimed at the current recipient?
    if (tf->header.type == TP_SINGLE_FRAME) {
        iso_tp_rx_single(sender_id, &tf->single);
        return;
    }

    // is this a first frame aimed at the current recipient?
    if (tf->header.type == TP_FIRST_FRAME) {
        iso_tp_rx_first(sender_id, &tf->first);
        return;
    }

    // is this a consecutive frame continuing reception?
    if (tf->header.type == TP_CONSECUTIVE_FRAME) {
        iso_tp_rx_consecutive(sender_id, &tf->consecutive);
        return;
    }
}

// Thread to handle periodic sending of ISO-TP consecutive frames.
//
void
iso_tp_sender(struct pt *pt)
{
    pt_begin(pt);
    tp_rx.resid = 1;    // initially have not received anything...

    for (;;) {
        // try sending another frame if transmission is in progress
        if (iso_tp_send_done() == ISO_TP_BUSY) {

            // try to send another frame
            iso_tp_tx_send_next();
        }
        pt_yield(pt);
    }

    pt_end(pt);
}
