/*
 * Input monitoring.
 */

#include <AD1.h>
#include <DO_30V_10V_1.h>

#include "timer.h"
#include "defs.h"

#define MON_AVG_SAMPLES         8

// order must match indices in AD1.h
static const uint16_t scale_factor[_MON_ID_MAX] = {
    ADC_SCALE_FACTOR_DO_V,
    ADC_SCALE_FACTOR_DO_V,
    ADC_SCALE_FACTOR_DO_I,
    ADC_SCALE_FACTOR_30V,
    ADC_SCALE_FACTOR_30V,
    ADC_SCALE_FACTOR_DO_V,
    ADC_SCALE_FACTOR_DO_V,
    ADC_SCALE_FACTOR_DO_I,
    ADC_SCALE_FACTOR_DO_I,
    ADC_SCALE_FACTOR_DO_I,
    ADC_SCALE_FACTOR_10V,
    ADC_SCALE_FACTOR_10V
};

static uint16_t mon_accum[MON_AVG_SAMPLES][_MON_ID_MAX];
static uint8_t mon_index;

static void
monitor_sample(void)
{
    (void)AD1_Measure(true);
    (void)AD1_GetValue(&mon_accum[mon_index][0]);
    if (++mon_index >= MON_AVG_SAMPLES) {
        mon_index = 0;
    }
}

void
monitor_init()
{
    static timer_call_t monitor_call;

    // set fuel level sensor to 10V mode
    DO_30V_10V_1_PutVal(FALSE);

    // register timer callback
    monitor_call.delay_ms = 1;
    monitor_call.callback = monitor_sample;
    monitor_call.period_ms = 5;
    timer_call_register(monitor_call);
}

uint16_t
monitor_get(monitor_channel_t channel)
{
    uint32_t scaled;
    uint16_t accum = 0;
    uint16_t result;
    uint8_t index;

    REQUIRE(channel < _MON_ID_MAX);

    // Accumulate samples, avoid racing with interrupt handler or 
    // holding it off for too long.
    //

    EnterCritical();
    for (index = 0; index < MON_AVG_SAMPLES; index++) {
        accum += mon_accum[index][channel];
    }
    ExitCritical();
    scaled = (uint32_t)accum * scale_factor[channel];

    result = (uint16_t)(scaled >> 12);
    return result;
}

void
monitor_test()
{
    print("val: %u", mon_accum[0][MON_FUEL_LEVEL]);
}