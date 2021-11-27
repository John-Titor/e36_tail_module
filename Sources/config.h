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
 * Interval (ms) between BMW module scans
 */
#define CAN_BMW_INTERVAL            200

/* 
 * Interval (ms) between status reports.
 */
#define CAN_REPORT_INTERVAL_STATE   100

/* 
 * Interval (ms) between CAN diagnostic messages.
 * 0 to disable.
 */
#define CAN_REPORT_INTERVAL_DIAGS   1000

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

/*
 * Timeout (ms) before deciding the scantool has disconnected.
 */
#define CAN_SCANTOOL_TIMEOUT        2000

#endif // _CONFIG_H
