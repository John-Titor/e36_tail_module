/*
 * General definitions.
 */

#ifndef _DEFS_H
#define _DEFS_H

#include <stdio.h>
#include <stdtypes.h>

#include <AD1.h>

#include "config.h"
#include "pt.h"


/*
 *  Minimal <stdint> types
 */

typedef unsigned char   uint8_t;
typedef unsigned int    uint16_t;
typedef unsigned long   uint32_t;

/* 
 * Library stuff.
 */
#define REQUIRE(_cond)                                      \
    do {                                                    \
        if (!(_cond))  __require_abort(__FILE__, __LINE__); \
    } while(0)

#define ABORT()     REQUIRE(0)

extern void __require_abort(const char *file, int line);
extern void print(const char *format, ...);

/*
 * Basic CAN things; listener, reporter, 
 * debug, etc.
 */

extern struct pt pt_can_listener;
extern struct pt pt_can_report_state;
extern struct pt pt_can_report_diags;

extern void can_trace(uint8_t code);
extern void can_putchar(char ch);

extern void can_reinit(void);
extern void can_rx_message(void);
extern void can_listen(struct pt *pt);
extern void can_report_state(struct pt *pt);
extern void can_report_diags(struct pt *pt);


/*
 * CAS / JBE emulator to enable ProTools
 */

extern struct pt pt_cas_jbe_emulator;

extern void cas_jbe_recv(uint8_t *data);
extern void cas_jbe_emulator(struct pt *pt);


/*
 * DDE scanner
 */

extern bool dde_oil_warning;
extern bool dde_mil_state;
extern struct pt pt_dde_scanner;
extern struct pt pt_can_report_dde;

extern void dde_recv(uint8_t *data);
extern void dde_scanner(struct pt *pt);
extern void dde_scanner(struct pt *pt);
extern void can_report_dde(struct pt *pt);


/*
 * Various light behaviours.
 */

extern struct pt pt_brakes;
extern struct pt pt_tails;
extern struct pt pt_rains;

typedef enum {
    LIGHT_OFF,
    LIGHT_ON,
    LIGHT_ALT,
    _LIGHT_STATE_MAX
} light_state_t;

extern light_state_t brake_light_requested;
extern light_state_t tail_light_requested;
extern light_state_t rain_light_requested;

extern void brake_thread(struct pt *pt);
extern void tails_thread(struct pt *pt);
extern void rains_thread(struct pt *pt);
extern void brake_light_request(light_state_t state);
extern void tail_light_request(light_state_t state);
extern void rain_light_request(light_state_t state);


/*
 * Analog monitors.
 */

// ADC scale factors
//
// Measurements in 10-bit mode.
//
// Scaling is performed by taking the accumulated ADC counts
// (sum of ADC_AVG_SAMPLES), multiplying by the scale factor
// and then right-shifting by 12, i.e. the scale factor is a
// 4.12 fixed-point quantity.
//
// To calculate the scaling factor, take mV-per-count and
// multiply by 512.
//
// Current sense outputs are the same but for mA.
//
// AI_1/2/3:
// --------
// 1K pullup mode: TBD
// 20mA mode: TBD (claimed 25mA)

#define ADC_SCALE_FACTOR_30V    17900U  // VALIDATED @ 4.860V
#define ADC_SCALE_FACTOR_10V    6065U   // VALIDATED @ 4.860V

// AI_OP_1/2/3/4:
// -------------

#define ADC_SCALE_FACTOR_DO_V   16494U  // VALIDATED @ 11.46V

// AI_CS_1/2/3/4:
// -------------

#define ADC_SCALE_FACTOR_DO_I   4531U   // VALIDATED @ 1.000A

// AI_KL15:
// -------
// Clamped at 11V; mostly useful to help detect input sag and
// avoid faulting outputs when T30 is low.
//

#define ADC_SCALE_FACTOR_KL15   5507U   // VALIDATED @ 8.368V

// AI_TEMP
// -------
// Calculated for nominal Vdd (5V)

#define ADC_SCALE_FACTOR_TEMP   610U    // XXX VALIDATE

// Order here must match numerical value of constants
// from AD1.h
typedef enum {
    MON_OUT_V_1         = AD1_CHANNEL_AI_OP_1,
    MON_OUT_V_2         = AD1_CHANNEL_AI_OP_2,
    MON_OUT_I_2         = AD1_CHANNEL_AI_CS_2,
    MON_AI_2            = AD1_CHANNEL_AI_2,
    MON_AI_3            = AD1_CHANNEL_AI_3,
    MON_OUT_V_3         = AD1_CHANNEL_AI_OP_3,
    MON_OUT_V_4         = AD1_CHANNEL_AI_OP_4,
    MON_OUT_I_1         = AD1_CHANNEL_AI_CS_1,
    MON_OUT_I_3         = AD1_CHANNEL_AI_CS_3,
    MON_OUT_I_4         = AD1_CHANNEL_AI_CS_4,
    MON_FUEL_LEVEL      = AD1_CHANNEL_AI_1,
    MON_T15_VOLTAGE     = AD1_CHANNEL_AI_KL15,
    _MON_ID_MAX
} monitor_channel_t;

extern void monitor_test(void);
extern void monitor_init(void);
extern uint16_t monitor_get(monitor_channel_t channel);


/*
 * High-side driver outputs.
 */

typedef enum {
    OUTPUT_BRAKE_L,     // left brake
    OUTPUT_BRAKE_R,     // right brake
    OUTPUT_TAILS,       // tail lights
    OUTPUT_RAINS,       // rain light(s)
    _OUTPUT_ID_MAX
} output_id_t;

typedef enum {
    OUTPUT_STATE_OFF,
    OUTPUT_STATE_ON,
    _OUTPUT_STATE_MAX
} output_state_t;

extern struct pt pt_output_0;
extern struct pt pt_output_1;
extern struct pt pt_output_2;
extern struct pt pt_output_3;
extern uint8_t output_pin_state;

extern void output_thread(struct pt *pt, output_id_t output);
extern void output_request(output_id_t output, output_state_t state); 


/*
 * Faults.
 *
 * XXX due to current encoding strategy, only 4 output
 *     and 4 system faults are supported
 */

typedef enum {
    OUT_FAULT_OPEN,
    OUT_FAULT_STUCK,
    OUT_FAULT_OVERLOAD,
    _OUT_FAULT_MAX,
} output_fault_t;

typedef enum {
    SYS_FAULT_T15_PLAUSIBILITY,
    SYS_FAULT_CAN_TIMEOUT,
    SYS_FAULT_OVER_TEMPERATURE,
    _SYS_FAULT_MAX,
} system_fault_t;

typedef union {
    struct {
        uint8_t     current: 4;
        uint8_t     latched: 4;
    } fields;
    uint8_t     raw;
} fault_status_t;

extern fault_status_t   fault_output[];
extern fault_status_t   fault_system;

extern void fault_set_output(output_id_t id, output_fault_t fault);
extern void fault_clear_output(output_id_t id, output_fault_t fault);
extern void fault_set_system(system_fault_t fault);
extern void fault_clear_system(system_fault_t fault);

#endif // _DEFS_H
