from qt import *
from HardwareRepository.BaseHardwareObjects import Equipment
import logging
import os
import time
import types
import gevent.event
import gevent

class XfeSpectrum(Equipment):
    def init(self):
        self.startXrfSpectrum = self.startXfeSpectrum
        self.cancelXrfSpectrum = self.cancelXfeSpectrum
         
        self.scanning = None
        self.moving = None
        self.ready_event = gevent.event.Event()

        self.storeSpectrumThread = None

        if True:
            try:
                self.energySpectrumArgs=self.getChannelObject('spectrum_args')
            except KeyError:
                logging.getLogger().warning('XRFSpectrum: error initializing energy spectrum arguments (missing channel)')
                self.energySpectrumArgs=None
            try:
                self.spectrumStatusMessage=self.getChannelObject('spectrumStatusMsg')
            except KeyError:
                self.spectrumStatusMessage=None
                logging.getLogger().warning('XRFSpectrum: energy messages will not appear (missing channel)')
            else:
                self.spectrumStatusMessage.connectSignal("update", self.spectrumStatusChanged)

            try:
                #self.doSpectrum.connectSignal('commandReplyArrived', self.spectrumCommandFinished)
                self.doSpectrum.connectSignal('commandBeginWaitReply', self.spectrumCommandStarted)
                self.doSpectrum.connectSignal('commandFailed', self.spectrumCommandFailed)
                self.doSpectrum.connectSignal('commandAborted', self.spectrumCommandAborted)
                self.doSpectrum.connectSignal('commandReady', self.spectrumCommandReady)
                self.doSpectrum.connectSignal('commandNotReady', self.spectrumCommandNotReady)
            except AttributeError,diag:
                logging.getLogger().warning('XRFSpectrum: error initializing energy spectrum (%s)' % str(diag))
                self.doSpectrum=None
            else:
                self.doSpectrum.connectSignal("connected", self.sConnected)
                self.doSpectrum.connectSignal("disconnected", self.sDisconnected)
 
            self.dbConnection=self.getObjectByRole("dbserver")
            if self.dbConnection is None:
                logging.getLogger().warning('XRFSpectrum: you should specify the database hardware object')
            self.spectrumInfo=None

            if self.isConnected():
               self.sConnected()


    def isConnected(self):
        try:
          return self.doSpectrum.isConnected()
        except:
          return False 


    # Handler for spec connection
    def sConnected(self):
        self.emit('connected', ())
        curr = self.getSpectrumParams()

    # Handler for spec disconnection
    def sDisconnected(self):
        self.emit('disconnected', ())

    # Energy spectrum commands
    def canSpectrum(self):
        if not self.isConnected():
            return False
        return self.doSpectrum is not None

    def startXfeSpectrum(self,ct,directory,prefix,session_id=None,blsample_id=None):
        self.spectrumInfo = {"sessionId": session_id}
        self.spectrumInfo["blSampleId"] = blsample_id
        if not os.path.isdir(directory):
            logging.getLogger().debug("XRFSpectrum: creating directory %s" % directory)
            try:
                os.makedirs(directory)
            except OSError,diag:
                logging.getLogger().error("XRFSpectrum: error creating directory %s (%s)" % (directory,str(diag)))
                self.spectrumStatusChanged("Error creating directory")
                return False
        curr = self.getSpectrumParams()

        try:
            curr["escan_dir"]=directory
            curr["escan_prefix"]=prefix
        except TypeError:
            curr={}
            curr["escan_dir"]=directory
            curr["escan_prefix"]=prefix

        a = directory.split(os.path.sep)
        suffix_path=os.path.join(*a[4:])
        if 'inhouse' in a :
            a_dir = os.path.join('/data/pyarch/', a[2], suffix_path)
        else:
            a_dir = os.path.join('/data/pyarch/',a[4],a[3],*a[5:])
        if a_dir[-1]!=os.path.sep:
            a_dir+=os.path.sep
        if not os.path.exists(a_dir):
            try:
                #logging.getLogger().debug("XRFSpectrum: creating %s", a_dir)
                os.makedirs(a_dir)
            except:
                try:
                    smis_name=os.environ["SMIS_BEAMLINE_NAME"].lower()
                    x,y=smis_name.split("-")
                    bldir=x+"eh"+y
                except:
                    bldir=os.environ["SMIS_BEAMLINE_NAME"].lower()
                tmp_dir = "/data/pyarch/%s" % bldir
                logging.getLogger().error("XRFSpectrum: error creating archive directory - the data will be saved in %s instead", tmp_dir)
        
        filename_pattern = os.path.join(directory, "%s_%s_%%02d" % (prefix,time.strftime("%d_%b_%Y")) )
        aname_pattern = os.path.join("%s/%s_%s_%%02d" % (a_dir,prefix,time.strftime("%d_%b_%Y")))

        filename_pattern = os.path.extsep.join((filename_pattern, "dat"))
        html_pattern = os.path.extsep.join((aname_pattern, "html"))
        aname_pattern = os.path.extsep.join((aname_pattern, "png"))
        filename = filename_pattern % 1
        aname = aname_pattern % 1
        htmlname = html_pattern % 1

        i = 2
        while os.path.isfile(filename):
            filename = filename_pattern % i
            aname = aname_pattern % i
            htmlname = html_pattern % i
            i=i+1

        self.spectrumInfo["filename"] = filename
        #self.spectrumInfo["scanFileFullPath"] = filename
        self.spectrumInfo["jpegScanFileFullPath"] = aname
        self.spectrumInfo["exposureTime"] = ct
        self.spectrumInfo["annotatedPymcaXfeSpectrum"] = htmlname
        logging.getLogger().debug("XRFSpectrum: archive file is %s", aname)

        gevent.spawn(self.reallyStartXfeSpectrum, ct, filename)
        
        return True
        
    def reallyStartXfeSpectrum(self, ct, filename):    
        try:
            res = self.doSpectrum(ct, filename, wait=True)
        except:
            logging.getLogger().exception('XRFSpectrum: problem calling spec macro')
            self.spectrumStatusChanged("Error problem spec macro")
        else:
            self.spectrumCommandFinished(res)

    def cancelXfeSpectrum(self, *args):
        if self.scanning:
            self.doSpectrum.abort()

    def spectrumCommandReady(self):
        if not self.scanning:
            self.emit('xfeSpectrumReady', (True,))
            self.emit('xrfSpectrumReady', (True,))
            self.emit('xrfScanReady', (True,))

    def spectrumCommandNotReady(self):
        if not self.scanning:
            self.emit('xfeSpectrumReady', (False,))
            self.emit('xrfSpectrumReady', (False,))
            self.emit('xrfScanReady', (False,))

    def spectrumCommandStarted(self, *args):
        self.spectrumInfo['startTime']=time.strftime("%Y-%m-%d %H:%M:%S")
        self.scanning = True
        self.emit('xfeSpectrumStarted', ())
        self.emit('xrfSpectrumStarted', ())
        self.emit('xrfScanStarted', ())

    def spectrumCommandFailed(self, *args):
        self.spectrumInfo['endTime']=time.strftime("%Y-%m-%d %H:%M:%S")
        self.scanning = False
        self.storeXfeSpectrum()
        self.emit('xfeSpectrumFailed', ())
        self.emit('xrfSpectrumFailed', ())
        self.emit('xrfScanFailed', ())
        self.ready_event.set()
    
    def spectrumCommandAborted(self, *args):
        self.scanning = False
        self.emit('xfeSpectrumFailed', ())
        self.emit('xrfSpectrumFailed', ())
        self.emit('xrfScanFailed', ())
        self.ready_event.set()

    def spectrumCommandFinished(self,result):
        self.spectrumInfo['endTime']=time.strftime("%Y-%m-%d %H:%M:%S")
        logging.getLogger().debug("XRFSpectrum: XRF spectrum result is %s" % result)
        self.scanning = False

        if result==0:
            mcaData = self.getChannelObject('mca_data').getValue()
            mcaCalib = self.getChannelObject('calib_data').getValue()
            mcaConfig = self.getChannelObject('config_data').getValue()
            self.spectrumInfo["beamTransmission"] = mcaConfig['att']
            self.spectrumInfo["energy"] = mcaConfig['energy']
            self.spectrumInfo["beamSizeHorizontal"] = float(mcaConfig['bsX'])
            self.spectrumInfo["beamSizeVertical"] = float(mcaConfig['bsY'])
            mcaConfig["legend"] = self.spectrumInfo["annotatedPymcaXfeSpectrum"]
                        
            #here move the png file
            pf = self.spectrumInfo["filename"].split(".")
            pngfile = os.path.extsep.join((pf[0], "png"))
            if os.path.isfile(pngfile) is True :
                try :
                    copy(pngfile,self.spectrumInfo["jpegScanFileFullPath"])
                except:
                    logging.getLogger().error("XRFSpectrum: cannot copy %s", pngfile)
            
            logging.getLogger().debug("finished %r", self.spectrumInfo)
            self.storeXfeSpectrum()
            self.emit('xfeSpectrumFinished', (mcaData,mcaCalib,mcaConfig))
            self.emit('xrfSpectrumFinished', (mcaData,mcaCalib,mcaConfig))
            self.emit('xrfScanFinished', (mcaData,mcaCalib,mcaConfig))
        else:
            self.spectrumCommandFailed()
        self.ready_event.set()
            
    def spectrumStatusChanged(self,status):
        self.emit('xrfScanStatusChanged', (status, ))
        self.emit('spectrumStatusChanged', (status,))

    def storeXfeSpectrum(self):
        logging.getLogger().debug("db connection %r", self.dbConnection)
        logging.getLogger().debug("spectrum info %r", self.spectrumInfo)
        if self.dbConnection is None:
            return
        try:
            session_id=int(self.spectrumInfo['sessionId'])
        except:
            return
        blsampleid=self.spectrumInfo['blSampleId']
        #self.spectrumInfo.pop('blSampleId')
        db_status=self.dbConnection.storeXfeSpectrum(self.spectrumInfo)

    def updateXfeSpectrum(self,spectrum_id,jpeg_spectrum_filename):
        pass

    def getSpectrumParams(self):
        try:
            self.curr=self.energySpectrumArgs.getValue()
            return self.curr
        except:
            logging.getLogger().exception('XRFSpectrum: error getting xrfspectrum parameters (%s)' % str(diag))
            self.spectrumStatusChanged("Error getting xrfspectrum parameters")
            return False

    def setSpectrumParams(self,pars):
        self.energySpectrumArgs.setValue(pars)

