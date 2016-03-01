# -*- coding: utf-8 -*-
'''Tango Shutter Hardware Object
Example XML:
<device class = "TangoShutter">
  <username>label for users</username>
  <command type="tango" tangoname="my device" name="Open">Open</command>
  <command type="tango" tangoname="my device" name="Close">Close</command>
  <channel type="tango" name="State" tangoname="my device" polling="1000">State</channel>
</device>

'''

from HardwareRepository import BaseHardwareObjects
import logging
import time

class SOLEILGuillotine(BaseHardwareObjects.Device):
    shutterState = {
        #0:  'ON',
        #1:  'OFF',
        'False':    'CLOSED',
        'True':     'OPENED',
        '0':        'CLOSED',
        '1':        'OPENED',
        '4':        'INSERT',
        '5':        'EXTRACT',
        '6':        'MOVING',
        '7':        'STANDBY',
        '8':        'FAULT',
        '9':        'INIT',
        '10':       'RUNNING',
        '11':       'ALARM',
        '12':       'DISABLED',
        '13':       'UNKNOWN',
        '-1':       'FAULT',
        'None':     'UNKNOWN',
        'UNKNOWN':  'UNKNOWN',
        'CLOSE':    'CLOSED',
        'OPEN':     'OPENED',
        'INSERT':   'CLOSED',
        'EXTRACT':  'OPENED',
        'MOVING':   'MOVING',
        'RUNNING':  'MOVING',
        '_':        'AUTOMATIC',
        'FAULT':    'FAULT',
        'DISABLE':  'DISABLED',
        'OFF':      'FAULT',
        'STANDBY':  'STANDBY',
        'ON':       'UNKNOWN',
        'ALARM':    'ALARM' 
        }
    #shutterState = {
            #None: 'unknown',
            #'UNKNOWN': 'unknown',
            #'CLOSE': 'closed',
            #'OPEN': 'opened',
            #'INSERT': 'closed',
            #'EXTRACT': 'opened',
            #'MOVING': 'moving',
            #'RUNNING':'moving',
            #'_': 'automatic',
            #'FAULT': 'fault',
            #'DISABLE': 'disabled',
            #'OFF': 'fault',
            #'STANDBY': 'standby',
            #'ON': 'unknown'
            #}
    shutterStateString = {
        'ON':        'white',
        'OFF':       '#012345',
        'CLOSED':    '#C03000',
        'CLOSE':     '#FF00FF',
        'OPEN':      '#00FF00',
        'OPENED':    '#00FF00', 
        'INSERT':    '#EC3CDD',
        'EXTRACT':   '#512345',
        'MOVING':    '#663300',
        'STANDBY':   '#009900',
        'FAULT':     '#990000',
        'INIT':      '#990000',
        'RUNNING':   '#990000',
        'ALARM':     '#990000',
        'DISABLED':  '#EC3CDD',
        'UNKNOWN':   'GRAY',
        'FAULT':     '#FF0000',
        }

    def __init__(self, name):
        BaseHardwareObjects.Device.__init__(self, name)
        logging.info("Guillotine init ")
        
    def init(self):
        self._shutterStateValue = 'UNKNOWN'
        self._currentDistance = 'None'
        self._d_security = self.getProperty('security_distance')
        self._d_home = self.getProperty('safe_distance')
        try:
            self.shutChannel = self.getChannelObject('State')
            self.shutChannel.connectSignal('update', self.shutterStateChanged)
            
            self.pss = self.getObjectByRole("pss")
            self.detector = self.getObjectByRole("detectordistance")
            self.md2_phase = self.getObjectByRole("md2j_phase")
            
            #self.connect(self.pss, 'wagoStateChanged', self.updateGuillotine)
            self.connect(self.detector, 'positionChanged', self.shutterStateChanged)
            self.connect(self.detector, 'positionChanged', self.updateDetectorDistance)
            self.connect(self.md2_phase, 'stateChanged', self.moveGuillotine)

            for command_name in ("_Insert","_Extract"):
                setattr(self, command_name, self.getCommandObject(command_name))
                               
        except KeyError:
            logging.getLogger().warning('%s: cannot report State', self.name())

    def shutterStateChanged(self, value):
        #
        # emit signal
        #
        if type(value) == float :
            value = self.shutChannel.value
        self.shutterStateValue = str(value)
        self.emit('shutterStateChanged', (self.getShutterState(),))

    def getShutterState(self):
        #if self.pss.getWagoState() != "ready":
        #    return "disabled"
        if not self.checkDistance() :
            return "disabled"
        return SOLEILGuillotine.shutterState.get(self.shutterStateValue, "UNKNOWN").lower()

    def updateDetectorDistance(self, value):
        self._currentDistance = value #self.detector.res2dist(value)
    
    def moveGuillotine(self, state):
        logging.info('>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>> GUILLOTINE..............changing state for %s.' % state)
        if state == 'Transfer' :
            self.goToSecurityDistance()
    
    def updateGuillotine(self,timeout=10.0):
        #if open door close guillotine but test distance
        #if distance security ok else move detector to security distance
        #wait until distance is reached
        if self.pss.getWagoState() != "ready":
            if self.checkDistance() :
                self.goToSecurityDistance()
                self.setIn()   
    def checkDistance(self):
        logging.info('Current distance is %s' % self._currentDistance)

        if self._currentDistance < self._d_security :
            return False
        else :
            return True

    def goToSecurityDistance(self):
        self.detector.move(self._d_home)
        if str(self.shutChannel.value) == 'EXTRACT':
            self._Insert()                
        while self.detector.motorIsMoving():
            time.sleep(0.5)

    def isShutterOk(self):
        return not self.getShutterState() in ('OFF', 'UNKNOWN', 'MOVING', 'FAULT', 'INSERT', 'EXTRACT',
                                              'INIT', 'DISABLED', 'ERROR', 'ALARM', 'STANDBY')            
    def openShutter(self):
        logging.info("Guillotine extract")
        if self.checkDistance():
            self._Extract()
            return
        logging.getLogger("user_level_log").error( " Detector is too closed to the gonio Guillotine couldn't be moved")
    
    def closeShutter(self):
        logging.info( "Guillotine insert")
        if self.checkDistance():
            self._Insert()
            return
        logging.getLogger("user_level_log").error( " Detector is too closed to the gonio Guillotine couldn't be moved")

    def setIn(self):
        self._Insert()

    def setOut(self):
        self._Extract()