#
#  Project: MXCuBE
#  https://github.com/mxcube.
#
#  This file is part of MXCuBE software.
#
#  MXCuBE is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  MXCuBE is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with MXCuBE.  If not, see <http://www.gnu.org/licenses/>.

"""
EMBLDoorInterlock
"""

import logging
import gevent
from HardwareRepository.BaseHardwareObjects import Device

import _tine as tine


__author__ = "Ivars Karpics"
__credits__ = ["MXCuBE colaboration"]

__version__ = "2.2."
__maintainer__ = "Ivars Karpics"
__email__ = "ivars.karpics[at]embl-hamburg.de"
__status__ = "Draft"


class EMBLDoorInterlock(Device):
    DoorInterlockState = {
        3: 'unlocked',
        1: 'closed',
        0: 'locked_active',
        46: 'locked_inactive',
        -1: 'error'
        }

    def __init__(self, name):
        Device.__init__(self, name) 

        self.door_interlock_state = None
        self.door_interlocked_cond = None
        self.door_interlocked_cond_value = None

        self.can_unlock_cond = None
        self.can_unlock_cond_value = None
        self.before_unlock_commands_present = None
        self.before_unlock_commands = None

        self.use_door_interlock = None
        self.cmd_break_interlock = None
        self.chan_can_unlock_cond = None
        self.chan_door_is_interlocked = None
        self.chan_door_is_interlocked = None
           
    def init(self):
        self.door_interlock_state = "unknown"

        self.can_unlock_cond_value = None
        self.can_unlock_cond = int(self.getProperty("canUnlockCond"))
        self.door_interlocked_cond_value = None
        self.door_interlocked_cond = int(self.getProperty("doorInterlockedCond"))

        self.before_unlock_commands_present = self.getProperty("before_unlock_commands_present")
        if self.before_unlock_commands_present:
            self.before_unlock_commands = self.getProperty("beforeUnlockCommands")

        self.use_door_interlock = self.getProperty('useDoorInterlock')
        if self.use_door_interlock is None:
            self.use_door_interlock = True

        self.cmd_break_interlock = self.getCommandObject('cmdBreakInterlock')
        self.chan_can_unlock_cond = self.getChannelObject('chanCanUnlockCond')
        if self.chan_can_unlock_cond is not None: 
            self.chan_can_unlock_cond.connectSignal('update', self.can_unlock_cond_changed)
        self.chan_door_is_interlocked = self.getChannelObject('chanDoorInterlocked')
        if self.chan_door_is_interlocked is not None:
            self.chan_door_is_interlocked.connectSignal('update', self.door_interlock_state_changed)

    def connected(self):
        self.setIsReady(True)

    def disconnected(self):
        self.setIsReady(False)

    def can_unlock_cond_changed(self, state):
        self.can_unlock_cond_value = int(state)
        self.get_state()

    def door_interlock_state_changed(self, state):
        #value = self.door_interlocked_cond_value
        self.door_interlocked_cond_value = int(state)
        #if (value != self.door_interlocked_cond_value):
        self.get_state()

    def door_interlock_can_unlock(self):
        return self.can_unlock_cond == self.can_unlock_cond_value

    def door_is_interlocked(self):
        return self.door_interlocked_cond == self.door_interlocked_cond_value 

    def getState(self):
        return self.door_interlock_state 

    def get_state(self): 
        if self.door_is_interlocked():
            if self.door_interlock_can_unlock():
                self.door_interlock_state = 'locked_active' 
                msg = "Locked (unlock enabled)"
            else:
                self.door_interlock_state = 'locked_inactive' 
                msg = "Locked (unlock disabled)"
        else:
            self.door_interlock_state = 'unlocked'
            msg = "Unlocked"

        if not self.use_door_interlock:
            self.door_interlock_state = 'locked_active'
            msg = "Locked (unlock enabled)"

        self.emit('doorInterlockStateChanged', self.door_interlock_state, msg)
        return self.door_interlock_state

    #  Break Interlock (only if it is allowed by doorInterlockCanUnlock) 
    #  It doesn't matter what we are sending in the command as long as it is a one char
    def unlock_door_interlock(self):
        if not self.use_door_interlock:
            logging.getLogger().info('Door interlock is disabled')
            return

        if self.door_is_interlocked():
            gevent.spawn(self.unlock_doors_thread)
        else:
            logging.getLogger().info('Door is Interlocked')
        
    def before_unlock_actions(self):
	if self.before_unlock_commands_present:
            for command in eval(self.before_unlock_commands):
                addr = command["address"]
                prop =  command["property"]
                if len(command["argument"]) == 0:
                    arg = [0]
                else:
                    try:
                        arg = [eval(command["argument"])]
                    except :
                        arg = [command["argument"]]
                if command["type"] == "set" :
                    tine.set(addr, prop, arg)	
                elif command["type"] == "query" :
                    tine.query(addr, prop, arg[0])

    def unlock_doors_thread(self):
        if self.door_interlock_can_unlock():
            try:
                self.before_unlock_actions()
                if self.cmd_break_interlock is None:
                    self.cmd_break_interlock = self.getCommandObject('cmdBreakInterlock') 
                self.cmd_break_interlock("b")
            except:
                logging.getLogger().error('Door interlock: unable to break door interlock.')
        else:
            msg = "Door Interlock cannot be broken at the moment " + \
                  "please check its status and try again."
            logging.getLogger("user_level_log").error(msg)
