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
 * Interval (ms) between CAN diagnostic messages.
 * 0 to disable.
 */
#define CAN_REPORT_INTERVAL_DIAGS   1000
#define CAN_ID_DIAGS                0x720

/* 
 * Interval (ms) between CAN status report messages
 * 0 to disable.
 */
#define CAN_REPORT_INTERVAL_STATE   200
#define CAN_ID_STATE                0x710

/*
 * Interval (ms) between BMW DDE poll events
 */
#define CAN_BMW_INTERVAL            100

/*
 * Base CAN ID for reflected BMW PID messages
 */
#define CAN_ID_BMW                  0x700

/*
 * Local ISO-TP node address
 */
#define ISO_TP_NODE_ID              0xf1

/*
 * Minimum load current (mA): below this, output is considered open.
 */
#define SENSE_OPEN_CURRENT          50

/*
 * Maximum load current (mA): over this, output is considered overloaded.
 */
#define SENSE_OVERLOAD_CURRENT      2500

/*
 * Maximum off voltage (mV): over this, output is considered stuck/shorted to +12.
 */
#define SENSE_STUCK_VOLTAGE         2000

/*
 * Inrush current settling time (ms)
 */
#define SENSE_INRUSH_DELAY          50

/*
 * Turn-off current settling time (ms)
 */
#define SENSE_SETTLE_DELAY          500

/*
 * Delay between retries for an overloaded output (ms).
 */
#define SENSE_OVERLOAD_RETRY_INTERVAL   1000


#endif // _CONFIG_H
