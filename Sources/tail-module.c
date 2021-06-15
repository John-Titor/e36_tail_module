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
struct pt pt_dde_scanner;
struct pt pt_cas_jbe_emulator;

struct pt pt_can_report_state;
struct pt pt_can_report_diags;

struct pt pt_brakes;
struct pt pt_tails;
struct pt pt_rains;
struct pt pt_output_0;
struct pt pt_output_1;
struct pt pt_output_2;
struct pt pt_output_3;

void
tail_module(void)
{
    (void)WDog1_Clear();

    // stay awake even if KL15 is not present
    DO_POWER_SetVal();

    // fix CAN config and hook up printf
    can_reinit();
    print("E36 tail module");

    // configure analog monitors
    monitor_init();

    // main loop
    for (;;) {
        (void)WDog1_Clear();                            // must be reset every 1s or better

        // listeners
        can_listen(&pt_can_listener);
        cas_jbe_emulator(&pt_cas_jbe_emulator);
        if (pt_running(&pt_dde_scanner)) {
            dde_scanner(&pt_dde_scanner);
        }

        // reporters
        can_report_state(&pt_can_report_state);
        can_report_diags(&pt_can_report_diags);

        // output handlers
        brake_thread(&pt_brakes);
        tails_thread(&pt_tails);
        rains_thread(&pt_rains);
        output_thread(&pt_output_0, 0);
        output_thread(&pt_output_1, 1);
        output_thread(&pt_output_2, 2);
        output_thread(&pt_output_3, 3);
    }
}

