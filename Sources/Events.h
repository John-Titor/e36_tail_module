/* ###################################################################
**     Filename    : Events.h
**     Project     : 7x_experiment
**     Processor   : MC9S08DZ60CLH
**     Component   : Events
**     Version     : Driver 01.02
**     Compiler    : CodeWarrior HCS08 C Compiler
**     Date/Time   : 2021-04-22, 15:59, # CodeGen: 0
**     Abstract    :
**         This is user's event module.
**         Put your event handler code here.
**     Settings    :
**     Contents    :
**         No public methods
**
** ###################################################################*/
/*!
** @file Events.h
** @version 01.02
** @brief
**         This is user's event module.
**         Put your event handler code here.
*/         
/*!
**  @addtogroup Events_module Events module documentation
**  @{
*/         

#ifndef __Events_H
#define __Events_H
/* MODULE Events */

#include "PE_Types.h"
#include "PE_Error.h"
#include "PE_Const.h"
#include "IO_Map.h"
#include "DI_CAN_ERR.h"
#include "AI_3_PU.h"
#include "CAN_EN.h"
#include "CAN_STB_N.h"
#include "CAN_WAKE.h"
#include "DO_20MA_1.h"
#include "DO_20MA_2.h"
#include "DO_30V_10V_1.h"
#include "DO_30V_10V_2.h"
#include "DO_30V_10V_3.h"
#include "DO_HSD_1.h"
#include "DO_HSD_2.h"
#include "DO_HSD_3.h"
#include "DO_HSD_4.h"
#include "DO_HSD_SEN.h"
#include "AD1.h"
#include "DO_POWER.h"
#include "CAN1.h"
#include "IEE1.h"
#include "TickTimer.h"
#include "WDog1.h"


void TickTimer_OnInterrupt(void);
/*
** ===================================================================
**     Event       :  TickTimer_OnInterrupt (module Events)
**
**     Component   :  TickTimer [TimerInt]
**     Description :
**         When a timer interrupt occurs this event is called (only
**         when the component is enabled - <Enable> and the events are
**         enabled - <EnableEvent>). This event is enabled only if a
**         <interrupt service/event> is enabled.
**     Parameters  : None
**     Returns     : Nothing
** ===================================================================
*/

void CAN1_OnFullRxBuffer(void);
/*
** ===================================================================
**     Event       :  CAN1_OnFullRxBuffer (module Events)
**
**     Component   :  CAN1 [FreescaleCAN]
**     Description :
**         This event is called when the receive buffer is full after a
**         successful reception of a message. The event is available
**         only if Interrupt service/event is enabled.
**     Parameters  : None
**     Returns     : Nothing
** ===================================================================
*/

/* END Events */
#endif /* __Events_H*/

/*!
** @}
*/
/*
** ###################################################################
**
**     This file was created by Processor Expert 10.3 [05.09]
**     for the Freescale HCS08 series of microcontrollers.
**
** ###################################################################
*/
