/*
 * Timers and timebase.
 */

#ifndef _TIMER_H
#define _TIMER_H

#include <Cpu.h>

#include "defs.h"

extern void timer_tick(void);

// one-shot timer
typedef struct _timer {
    struct _timer       *_next;
    volatile uint16_t   delay_ms;
} timer_t;

// one-shot or periodic timer callback
typedef struct _timer_call {
    struct _timer_call  *_next;
    volatile uint16_t   delay_ms;
    void                (*callback)(void);      // function to call - must be interrupt-safe
    uint16_t            period_ms;              // tick interval between calls, 0 for one-shot
} timer_call_t;

// register a one-shot timer
#define timer_register(_t)      _timer_register(&_t)
extern void                     _timer_register(timer_t *timer);

// register a timer callback
#define timer_call_register(_t) _timer_call_register(&_t)
extern void                     _timer_call_register(timer_call_t *call);

// reset a one-shot timer or timer callback
#define timer_reset(_timer, _delay)     \
    do {                                \
        EnterCritical();                \
        (_timer).delay_ms = _delay;     \
        ExitCritical();                 \
    } while(0)

// test whether a timer or callback has expired
#define timer_expired(_timer)           ((_timer).delay_ms == 0)

// test whether a timer has been registered
// normally not required, as timer_register is a NOP on an already-registered
// timer
#define timer_registered(_timer)        ((_timer)._next != NULL)

// blocking delay for protothreads
#define pt_delay(pt, timer, ms)                                                 \
    do {                                                                        \
        timer_reset(timer, ms);                                                 \
        pt_wait(pt, timer_expired(timer));                                      \
    } while(0)

#endif // _TIMER_H
