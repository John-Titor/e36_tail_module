/*
 * Generic library-ish things.
 */

#include <assert.h>

#include "defs.h"


void
print(const char *format, ...)
{
    va_list args;

    set_printf(can_putchar);
    va_start(args, format);
    (void)vprintf(format, args);
    va_end(args);
    can_putchar('\n');
}

void
__require_abort(const char *file, int line)
{
    print("ABORT: %s:%d", file, line);
    for (;;);
}

