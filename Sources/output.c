/*
 * High-side drivers.
 *
 * ref: VNQ5050AK-E datasheet
 */

#include <DO_HSD_1.h>
#include <DO_HSD_2.h>
#include <DO_HSD_3.h>
#include <DO_HSD_4.h>

#include "timer.h"
#include "defs.h"

uint8_t output_pin_state;

static struct {
    output_state_t      state;
//    uint8_t             stuck_counter;
//    uint8_t             overload_counter;
//    uint8_t             open_counter;
    timer_t             timer;
} output_context[_OUTPUT_ID_MAX];

static uint16_t output_voltage(output_id_t output);
static uint16_t output_current(output_id_t output);
static void     output_control(output_id_t output, bool on);


void
output_request(output_id_t output, output_state_t state)
{
    REQUIRE(output < _OUTPUT_ID_MAX);
    REQUIRE(state < _OUTPUT_STATE_MAX);

    // If this is a state change, reset the thread.
    //
    if (output_context[output].state != state) {
        output_context[output].state = state;
//        output_context[output].stuck_counter = 0;
//        output_context[output].overload_counter = 0;
//        output_context[output].open_counter = 0;
        switch (output) {
        case 0: pt_reset(&pt_output_0); break;
        case 1: pt_reset(&pt_output_1); break;
        case 2: pt_reset(&pt_output_2); break;
        case 3: pt_reset(&pt_output_3); break;
        }
    }
}

void
output_thread(struct pt *pt, output_id_t output)
{
    REQUIRE(output < _OUTPUT_ID_MAX);

    // lazy-register the output's timer
    //
    if (!timer_registered(output_context[output].timer)) {
        timer_register(output_context[output].timer);
    }

    pt_begin(pt);

    // Output-off behaviour.
    //
    if (output_context[output].state == OUTPUT_STATE_OFF) {

        // turn the pin off
        output_control(output, FALSE);

        // clear faults that can only be present when on
        fault_clear_output(output, OUT_FAULT_OPEN);

        // wait out the settling delay
        //
        pt_delay(pt, output_context[output].timer, SENSE_SETTLE_DELAY);

        // Sit in a loop checking for 'stuck' and 'overload'
        // status.
        //
        for (;;) {
            pt_yield(pt);

            // Check for stuck-on output
            //
            if (output_voltage(output) < SENSE_STUCK_VOLTAGE) {
                fault_clear_output(output, OUT_FAULT_STUCK);
            } else {
                fault_set_output(output, OUT_FAULT_STUCK);
            }    

            // Check for overload (only if output is stuck on due
            // to internal failure).
            //
            if (output_current(output) < SENSE_OVERLOAD_CURRENT) {
                fault_clear_output(output, OUT_FAULT_OVERLOAD);
            } else {
                fault_set_output(output, OUT_FAULT_OVERLOAD);
            }
        }
    }

    // Output-on behaviour
    //
    else if (output_context[output].state == OUTPUT_STATE_ON) {

        // turn the pin on
        output_control(output, TRUE);

        // clear faults that can only be present when off
        fault_clear_output(output, OUT_FAULT_STUCK);

        // wait out the inrush delay
        //
        pt_delay(pt, output_context[output].timer, SENSE_INRUSH_DELAY);

        // Sit in a loop checking for 'open' and 'overload'
        // status.
        //
        for (;;) {
            pt_yield(pt);

            // Check for open-circuit output
            //
            if (output_current(output) > SENSE_OPEN_CURRENT) {
                fault_clear_output(output, OUT_FAULT_OPEN);
            } else {
                fault_set_output(output, OUT_FAULT_OPEN);
            }    

            // Check for overload.
            //
            if (output_current(output) < SENSE_OVERLOAD_CURRENT) {
                fault_clear_output(output, OUT_FAULT_OVERLOAD);
            } else {
                fault_set_output(output, OUT_FAULT_OVERLOAD);

                // disable output
                output_control(output, FALSE);
                pt_delay(pt, output_context[output].timer, SENSE_OVERLOAD_RETRY_INTERVAL);
                output_control(output, TRUE);
            }
        }
    }

    pt_end(pt);
}

static uint16_t
output_voltage(output_id_t output)
{
    switch (output) {
    case 0: return monitor_get(MON_OUT_V_1);
    case 1: return monitor_get(MON_OUT_V_2);
    case 2: return monitor_get(MON_OUT_V_3);
    case 3: return monitor_get(MON_OUT_V_4);
    default: return 0;
    }
}

static uint16_t
output_current(output_id_t output)
{
    switch (output) {
    case 0: return monitor_get(MON_OUT_I_1);
    case 1: return monitor_get(MON_OUT_I_2);
    case 2: return monitor_get(MON_OUT_I_3);
    case 3: return monitor_get(MON_OUT_I_4);
    default: return 0;
    }
}

static void
output_control(output_id_t output, bool on)
{
    REQUIRE(output < _OUTPUT_ID_MAX);
    switch (output) {
    case 0: DO_HSD_1_PutVal(on); break;
    case 1: DO_HSD_2_PutVal(on); break;
    case 2: DO_HSD_3_PutVal(on); break;
    case 3: DO_HSD_4_PutVal(on); break;
    }
    if (on) {
        output_pin_state |= ((uint8_t)1 << output);
    } else {
        output_pin_state &= ~((uint8_t)1 << output);
    }
}
