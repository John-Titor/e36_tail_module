/*
 * Timers and timebase
 *
 * Using TPM2C2
 *
 * FFCLK is 1MHz, so we run with a /1 prescaler to count microseconds.
 *
 * We maintain a 32-bit timebase which will wrap after ~71 minutes,
 * so code must be careful about absolute time values.
 *
 * A note on time_wait_us: the maximum delay is limited to u_int16 both
 * for efficiency (waiting longer than 64ms is not friendly to other parts
 * of the system) and also to make it safe to use in a __critical region;
 * time_us can only handle one wrap before it needs the overflow handler to
 * run and adjust the timebase high word.
 *
 */

#include "timer.h"

#define TIMER_LIST_END      (timer_t *)1
#define TIMER_CALL_LIST_END (timer_call_t *)2

static timer_t          *timer_list = TIMER_LIST_END;
static timer_call_t     *timer_call_list = TIMER_CALL_LIST_END;

void
_timer_register(timer_t *timer)
{
    REQUIRE(timer != NULL);

    EnterCritical();

    if (!timer_registered(*timer)) {
        // singly-linked insertion at head
        timer->_next = timer_list;
        timer_list = timer;
    }

    ExitCritical();
}

void
_timer_call_register(timer_call_t *call)
{
    EnterCritical();

    REQUIRE(call != NULL);
    REQUIRE(call->callback != NULL);

    if (!timer_registered(*call)) {

        // singly-linked insertion at head
        call->_next = timer_call_list;
        timer_call_list = call;
    }   

    ExitCritical();
}

void
timer_tick(void)
{
    timer_t *t;
    timer_call_t *tc;

    // update timers
    for (t = timer_list; t != TIMER_LIST_END; t = t->_next) {
        if (t->delay_ms > 0) {
            t->delay_ms--;
        }
    }

    // run timer calls
    for (tc = timer_call_list; tc != TIMER_CALL_LIST_END; tc = tc->_next) {

        // if the call is active...
        if (tc->delay_ms > 0) {
            // and the delay expires...
            if (--tc->delay_ms == 0) {
                // run the callback
                tc->callback();
                // and reload the delay (or leave it at
                // zero for a one-shot)
                tc->delay_ms = tc->period_ms;
            }
        }
    }
}
