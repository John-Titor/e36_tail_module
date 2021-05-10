/*
 * Configuration parameters.
 */

#ifndef _CONFIG_H
#define _CONFIG_H

/* 
 * Timeout (ms) before deciding that CAN has been disconnected.
 */
#define CAN_IDLE_TIMEOUT            2000

/* 
 * Interval (ms) between fuel level reports
 */
#define CAN_REPORT_INTERVAL_FUEL    500

/* 
 * Interval (ms) between CAN diagnostic messages.
 * 0 to disable.
 */
#define CAN_REPORT_INTERVAL_DIAGS   1000

/*
 * Interval (ms) between console status reports.
 * 0 to disable.
 */
#define CONSOLE_REPORT_INTERVAL     1000

/*
 * Minimum load current (mA): below this, output is considered open.
 */
#define SENSE_OPEN_CURRENT      50

/*
 * Maximum load current (mA): over this, output is considered overloaded.
 */
#define SENSE_OVERLOAD_CURRENT  2500

/*
 * Maximum off voltage (mV): over this, output is considered stuck/shorted to +12.
 */
#define SENSE_STUCK_VOLTAGE     2000

/*
 * Number of successive stuck / overloaded / open tests required to
 * trigger the fault.
 */
#define SENSE_DEBOUNCE_COUNT    3

/*
 * Inrush current settling time (ms)
 */
#define SENSE_INRUSH_DELAY      50

/*
 * Turn-off current settling time (ms)
 */
#define SENSE_SETTLE_DELAY      500

/*
 * Delay between retries for an overloaded output (ms).
 */
#define SENSE_OVERLOAD_RETRY_INTERVAL   1000

/*
 * T15 brown-out voltage (mV).
 * Below this voltage the unit will not function; it
 * sits and waits for either the voltage to fall (so that it
 * powers off), or recover (at which point it will reset).
 */
#define T15_MIN_VOLTAGE         6000

#endif // _CONFIG_H
