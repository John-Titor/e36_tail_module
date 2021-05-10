/*
 * Faults.
 *
 * Current status is what's being reported right now,
 * and may fluctuate depending on what the system is
 * doing. Latched status is set once and never cleared.
 */

#include "defs.h"

fault_status_t  fault_output[_OUTPUT_ID_MAX];
fault_status_t  fault_system;

void
fault_set_output(output_id_t id, output_fault_t fault)
{
    REQUIRE(id < _OUTPUT_ID_MAX);
    REQUIRE(fault < _OUT_FAULT_MAX);

    fault_output[id].fields.current |= (1 << fault);
    fault_output[id].fields.latched |= (1 << fault);
}

void
fault_clear_output(output_id_t id, output_fault_t fault)
{
    REQUIRE(id < _OUTPUT_ID_MAX);
    REQUIRE(fault < _OUT_FAULT_MAX);

    fault_output[id].fields.current &= ~(1 << fault);
}

void
fault_set_system(system_fault_t fault)
{
    REQUIRE(fault < _SYS_FAULT_MAX);

    fault_system.fields.current |= (1 << fault);
    fault_system.fields.latched |= (1 << fault);
}

void
fault_clear_system(system_fault_t fault)
{
    REQUIRE(fault < _SYS_FAULT_MAX);

    fault_system.fields.current &= ~(1 <<  fault);
}

