/*
 * CAN messaging
 */

#include <stdio.h>

#include <CAN1.h>

#include "defs.h"
#include "pt.h"
#include "timer.h"

typedef struct {
    uint32_t    id;
    uint8_t     dlc;
    uint8_t     data[8];
}                           can_buf_t;

#define CAN_BUF_COUNT       8
static can_buf_t            _can_buf[CAN_BUF_COUNT];
static volatile uint8_t     can_buf_head;
static uint8_t              can_buf_tail;
#define _CAN_BUF_INDEX(_x)  ((_x) & (uint8_t)(CAN_BUF_COUNT - 1))
#define CAN_BUF_PTR(_x)     &_can_buf[_CAN_BUF_INDEX(_x)]
#define CAN_BUF_EMPTY       (can_buf_head == can_buf_tail)
#define CAN_BUF_FULL        ((can_buf_head - can_buf_tail) >= CAN_BUF_COUNT)

void
can_trace(uint8_t code)
{
    uint8_t b[1];
    uint8_t ret;

    b[0] = code;
    do {
        ret = CAN1_SendFrameExt(0x0f, DATA_FRAME, 0x1, &b[0]);
    } while (ret != ERR_OK);
}

void
can_putchar(char ch)
{
    static uint8_t msg[8];
    static uint8_t len = 0;
    uint8_t ret;

    if (ch == '\n') {
        ch = '\0';
    }
    msg[len++] = (uint8_t)ch;
    if ((len == 8) || (ch == '\0')) {
        do {
            // send explicitly using buffer 0 to ensure messages are sent in order
            ret = CAN1_SendFrame(0, CAN_EXTENDED_FRAME_ID | 0x1ffffffe, DATA_FRAME, len, &msg[0]);
        } while (ret == ERR_TXFULL);
        len = 0;
    }
}

/*
 * Processor Expert generates bogus config; fix it up here.
 */
void
can_reinit(void)
{
    REQUIRE(CAN_BUF_EMPTY);

    CANCTL0 |= CANCTL0_INITRQ_MASK;
    while (!(CANCTL1 & CANCTL1_INITAK_MASK)) {
    }

    // enable MSCAN, select external clock
    CANCTL1 = CANCTL1_CANE_MASK;

    // configure for 125kbps
    //CANBTR0 = 0x03;
    // configure for 500kbps
    CANBTR0 = 0x00;

    CANBTR1 = 0x1c;

    // configure filters
    CANIDAC = 0x10;             // 4x16 filters

    CANIDAR0 = 0x15;            // 0x0a8
    CANIDAR1 = 0x00;
    CANIDMR0 = 0xff;
    CANIDMR1 = 0xe0;

    CANIDAR2 = 0x43;            // 0x21a
    CANIDAR3 = 0x40;
    CANIDMR2 = 0xff;
    CANIDMR3 = 0xe0;

    CANIDAR4 = 0xde;            // 0x6xx
    CANIDAR5 = 0x20;
    CANIDMR4 = 0xe0;
    CANIDMR5 = 0x00;

    CANIDAR6 = 0x00;            // 0x000
    CANIDAR7 = 0x00;
    CANIDMR6 = 0xff;
    CANIDMR7 = 0xe0;

    // clear INITRQ and wait for it to be acknowledged
    CANCTL0 &= ~CANCTL0_INITRQ_MASK;
    while (CANCTL1 & CANCTL1_INITAK_MASK) {
    }
    CANRFLG |= 0xFE;                     /* Reset error flags */
    CANRIER = 0x01;                      /* Enable interrupts */

    // now we can enable RX events
    CAN1_EnableEvent();
}

/*
 * Interrupt callback for CAN receive.
 */
void
can_rx_message(void)
{
    // check for a CAN message
    can_buf_t *buf;
    uint8_t type;
    uint8_t ret;
    uint8_t format;

    // If there's nowhere to put a message, just drop it.
    if (CAN_BUF_FULL) {
        return;
    }
    buf = CAN_BUF_PTR(can_buf_head);

    // read the frame
    ret = CAN1_ReadFrame(&buf->id,
                         &type,
                         &format,
                         &buf->dlc,
                         &buf->data[0]);

    if ((ret == ERR_OK) &&
        (type == DATA_FRAME) &&
        (format == STANDARD_FORMAT)) {

        // accept this message
        can_buf_head++;
    }
}

void
can_listen(struct pt *pt)
{
    static timer_t  can_idle_timer;

    pt_begin(pt);

    // set up the CAN idle timer
    timer_register(can_idle_timer);
    timer_reset(can_idle_timer, CAN_IDLE_TIMEOUT);

    for (;;) {

        // handle CAN messages
        while (!CAN_BUF_EMPTY) {
            can_buf_t *buf = CAN_BUF_PTR(can_buf_tail);
            can_buf_tail++;

            // we're hearing CAN, so reset the idle timer / fault
            timer_reset(can_idle_timer, CAN_IDLE_TIMEOUT);
            fault_clear_system(SYS_FAULT_CAN_TIMEOUT);

            // BMW brake pedal message
            //
            if ((buf->id == 0xa8) &&
                (buf->dlc == 8)) {

                brake_light_request((buf->data[7] & 0x20) ? LIGHT_ON : LIGHT_OFF);
            }

            // BMW lighting message
            //
            else if ((buf->id == 0x21a) &&
                     (buf->dlc == 3)) {

                tail_light_request((buf->data[0] & 0x04) ? LIGHT_ON : LIGHT_OFF);
                rain_light_request((buf->data[0] & 0x40) ? LIGHT_ON : LIGHT_OFF);
            }

            // EDIABAS-style request
            else if ((buf->id == 0x6f1) &&
                     (buf->dlc == 8)) {

                cas_jbe_recv(&buf->data[0]);
            }

            // DDE response
            else if ((buf->id == 0x612) &&
                     (buf->dlc == 8)) {

                dde_recv(&buf->data[0]);
            }
        }

        // if we haven't heard a useful CAN message for a while...
        if (timer_expired(can_idle_timer)) {
            fault_set_system(SYS_FAULT_CAN_TIMEOUT);
            brake_light_request(LIGHT_ALT);
        }

        pt_yield(pt);
    }
    pt_end(pt);
}

void
can_report_state(struct pt *pt)
{
    static timer_t can_report_state_timer;

    pt_begin(pt);
    timer_register(can_report_state_timer);

    // loop forever sending state messages at the specified interval
    for (;;) {
        uint16_t mon_val;
        uint8_t data[8];
        uint8_t ret;

        pt_delay(pt, can_report_state_timer, CAN_REPORT_INTERVAL_STATE);

        // 0x702 - misc status

        // Convert 0.5-4.5 to 0-100% for fuel level
        mon_val = monitor_get(MON_FUEL_LEVEL);
        if (mon_val < 500) {
            data[0] = 0;
        } else if (mon_val > 4500) {
            data[0] = 100;
        } else {
            data[0] = (uint8_t)((mon_val - 500) / 40);
        }

        data[1] = data[2] = data[3] = data[4] = data[5] = data[6] = 0;

        // flags
        data[7] = 
            (dde_oil_warning ? 0x40 : 0x00) |
            (dde_mil_state ? 0x80 : 0x00);

        do {
            ret = CAN1_SendFrameExt(0x702, DATA_FRAME, 8, &data[0]);
        } while (ret == ERR_TXFULL);

    }
    pt_end(pt);
}

void
can_report_diags(struct pt *pt)
{
    static timer_t can_report_diags_timer;

    pt_begin(pt);
    timer_register(can_report_diags_timer);

    // loop forever sending diagnostic messages
    for (;;) {
        uint16_t mon_val;
        uint8_t data[8];
        uint8_t ret;

        pt_delay(pt, can_report_diags_timer, CAN_REPORT_INTERVAL_DIAGS);
        
        data[0] = 0;
        data[1] = 0;
        mon_val = monitor_get(MON_T15_VOLTAGE);
        data[2] = mon_val >> 8;
        data[3] = mon_val & 0xff;
#if 0
        mon_val = monitor_get(MON_TEMPERATURE);
        if (mon_val < 1396) {
            // not interesting
            mon_val = 0;
        } else {
            mon_val -= 1396;    // Vtemp25
            mon_val *= 275;     // scale to mC°
            mon_val /= 1000;    // back to C°
            mon_val += 25;      // offset
        }
        data[4] = mon_val; // TEMPERATURE
#endif
        data[4] = 0; // TEMPERATURE
        mon_val = monitor_get(MON_FUEL_LEVEL);
        data[5] = (uint8_t)(mon_val / 50); // scale 0-5000 -> %
        data[6] = output_pin_state;
        data[7] = ((brake_light_requested ? 1 : 0) |
                   (tail_light_requested ? 2 : 0) |
                   (rain_light_requested ? 4 : 0));

        do {
            ret = CAN1_SendFrameExt(CAN_EXTENDED_FRAME_ID | 0x0f00000, DATA_FRAME, 0x8, &data[0]);
        } while (ret == ERR_TXFULL);
        pt_yield(pt);

        mon_val = monitor_get(MON_OUT_V_1);
        data[0] = (uint8_t)(mon_val / 100);
        mon_val = monitor_get(MON_OUT_V_2);
        data[1] = (uint8_t)(mon_val / 100);
        mon_val = monitor_get(MON_OUT_V_3);
        data[2] = (uint8_t)(mon_val / 100);
        mon_val = monitor_get(MON_OUT_V_4);
        data[3] = (uint8_t)(mon_val / 100);
        mon_val = monitor_get(MON_OUT_I_1);
        data[4] = (uint8_t)(mon_val / 10);
        mon_val = monitor_get(MON_OUT_I_2);
        data[5] = (uint8_t)(mon_val / 10);
        mon_val = monitor_get(MON_OUT_I_3);
        data[6] = (uint8_t)(mon_val / 10);
        mon_val = monitor_get(MON_OUT_I_4);
        data[7] = (uint8_t)(mon_val / 10);

        do {
            ret = CAN1_SendFrameExt(CAN_EXTENDED_FRAME_ID | 0x0f00001, DATA_FRAME, 8, &data[0]);
        } while (ret == ERR_TXFULL);
        pt_yield(pt);

        data[0] = fault_output[0].raw;
        data[1] = fault_output[1].raw;
        data[2] = fault_output[2].raw;
        data[3] = fault_output[3].raw;
        data[4] = 0x11;
        data[5] = 0x22;
        data[6] = 0x33;
        data[7] = fault_system.raw;

        do {
            ret = CAN1_SendFrameExt(CAN_EXTENDED_FRAME_ID | 0x0f00002, DATA_FRAME, 8, &data[0]);
        } while (ret == ERR_TXFULL);
    }
    pt_end(pt);
}
