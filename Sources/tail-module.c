/*
 * Tail module for the Hello Kitty E36.
 *
 * Responsible for brake / rain / running lights,
 * also reading and reporting the fuel level from
 * a 0-5V fuel level sender.
 */

#include <stdio.h>

#include <DO_POWER.h>
#include <CAN_STB_N.h>
#include <CAN1.h>
#include <WDog1.h>

#include "pt.h"
#include "timer.h"
#include "defs.h"

struct pt pt_can_listener;
struct pt pt_can_report_fuel;
struct pt pt_can_report_diags;
struct pt pt_cas_jbe_emulator;
struct pt pt_brakes;
struct pt pt_tails;
struct pt pt_rains;
struct pt pt_output_0;
struct pt pt_output_1;
struct pt pt_output_2;
struct pt pt_output_3;

static void kl15_check(void);

void
tail_module(void)
{
    (void)WDog1_Clear();

    // stay awake even if KL15 is not present
    DO_POWER_SetVal();

    // hook up printf
    can_reinit();
    print("E36 tail module");

    // configure analog monitors
    monitor_init();

    // main loop
    for (;;) {
        (void)WDog1_Clear();                            // must be reset every 1s or better
        //kl15_check();                                 // XXX fix monitors

        // run threads
        can_listen(&pt_can_listener);
        can_report_fuel(&pt_can_report_fuel);
        can_report_diags(&pt_can_report_diags);
        cas_jbe_emulator(&pt_cas_jbe_emulator);
        brake_thread(&pt_brakes);
        tails_thread(&pt_tails);
        rains_thread(&pt_rains);
        output_thread(&pt_output_0, 0);
        output_thread(&pt_output_1, 1);
        output_thread(&pt_output_2, 2);
        output_thread(&pt_output_3, 3);
    }
}

void
kl15_check(void)
{
    if (monitor_get(MON_T15_VOLTAGE) >= T15_MIN_VOLTAGE) {
        return;
    }
    print("LVD");

    // low-voltage trap
    while (monitor_get(MON_T15_VOLTAGE) < T15_MIN_VOLTAGE) {
        // allow power-off if T15 falls low enough
        DO_POWER_ClrVal();
        CAN_STB_N_ClrVal();
        (void)WDog1_Clear();
    }

    // voltage has recovered, let the watchdog reset us
    for (;;);
}
