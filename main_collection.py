from radarHandler import CollectionThreadX4
import time
import os
import collections
import csv
import configparser
import threading
import queue
import sys

class MainClass:
    def __init__(self):
        self.configparser = configparser.ConfigParser()
        self.configparser.read('config.ini')
        self.config = self.configparser[self.configparser['DEFAULT']['config_to_use']]

        self.radar_fs = self.config.getfloat('radar_fs', 17.0)
        self.createRadarSettingsDict('x4')
        self.stopEvent = threading.Event()
        self.resumeEvent = threading.Event()
        self.resumeEvent.set()
        self.radarBuffer = queue.Queue()
        self.radarThread = CollectionThreadX4(threadID=1, name='radarThreadX4', radarBuffer=self.radarBuffer,
                                              stopEvent=self.stopEvent, radarSettings=self.radarSettings,
                                              baseband=True, fs=self.radar_fs, resumeEvent=self.resumeEvent)

        self.radar_data_dir = self.config.get('store_radar_data_in') + time.strftime(u"%Y%m%d")
        self.depth_data_dir = self.config.get('store_depth_data_in') + time.strftime(u"%Y%m%d")

        if not os.path.exists(self.radar_data_dir):
            os.makedirs(self.radar_data_dir)
        self.radar_data_dir = self.radar_data_dir + '/'

        if not os.path.exists(self.depth_data_dir):
            os.makedirs(self.depth_data_dir)
        self.depth_data_dir = self.depth_data_dir + '/'

        self.radar_file_name = self.config.get('radar_file_name')
        self.depth_file_name = self.config.get('depth_file_name')
        self.FILE_LENGTH = self.config.getint('file_length', 60)  # length of file to save in seconds
        self.SAVE_RADAR = True

        self.procInputDict = {}
        self.procInputDict['radarData'] = []
        self.radarDataDeck = collections.deque(maxlen=int(self.FILE_LENGTH * self.radar_fs * 2))  # deque is made with 2x required capacity

        self.cameraStopEvent = threading.Event()
        self.cameraBuffer = queue.Queue()
       
   self.processing_interval = self.config.getfloat('processing_interval', 1.0)

    def createRadarSettingsDict(self, moduleName):
        self.radarSettings = {}
        if moduleName == 'x2':
            self.radarSettings['PGSelect'] = 6
            self.radarSettings['FrameStitch'] = 3
            self.radarSettings['SampleDelayToReference'] = 2.9e-9
            self.radarSettings['Iterations'] = 50
            self.radarSettings['DACStep'] = 4
            self.radarSettings['DACMin'] = 0
            self.radarSettings['DACMax'] = 8191
            self.radarSettings['PulsesPerStep'] = 16
            self.radarSettings['RADAR_RESOLUTION'] = 3.90625 / 1000  # X2
            self.radarSettings['RadarType'] = 'X2'
        elif moduleName == 'x4':
            self.radarSettings['Iterations'] = 16 // can be changed to iterations as required 
            self.radarSettings['DACMin'] = 949
            self.radarSettings['DACMax'] = 1100
            self.radarSettings['PulsesPerStep'] = 26
            self.radarSettings['FrameStart'] = 0
            self.radarSettings['FrameStop'] = 9.75
            self.radarSettings['DACStep'] = 1  # This value is NOT USED. Just put here for the normalization
            self.radarSettings['RADAR_RESOLUTION'] = 51.8617 / 1000  # X4
            self.radarSettings['RadarType'] = 'X4'
        self.RADAR_RESOLUTION = self.radarSettings['RADAR_RESOLUTION']

    def main(self):
        global radarDataQ
        self.radarThread.start()
        #self.cameraThread.start()
        time.sleep(5)
        try:
            elapsedTime = 0
            while True:
                sleepTime = self.processing_interval - elapsedTime
                # print('Sleeping : %f seconds' % sleepTime)
                if sleepTime > 0:
                    time.sleep(sleepTime)
                startTime = time.time()
                while not self.radarBuffer.empty():
                    buffer = self.radarBuffer.get()
                    if buffer != 'setup_error':
                        self.procInputDict['radarData'].append(self.radarBuffer.get())
                    else:
                        print('radar thread has stopped, exiting program')
                        self.safeExit()
                self.radarDataDeck.extend(self.procInputDict['radarData'])  # Needed for saving the data

                cameraFrames = []
               # while not self.cameraBuffer.empty():
                #    cameraFrames.append(self.cameraBuffer.get())
               # self.cameraDeck.extend(cameraFrames)
                if self.SAVE_RADAR and len(self.radarDataDeck)>0:
                    # print(f'deck length: {len(self.radarDataDeck)}')
                    if isinstance(self.radarDataDeck[-1][0], complex):
                        if self.radarDataDeck[-1][0].real - self.radarDataDeck[0][0].real > self.FILE_LENGTH * 1000:
                            self.saveData()
                    else:
                        if self.radarDataDeck[-1][0] - self.radarDataDeck[0][0] > self.FILE_LENGTH * 1000:
                            self.saveData()
                self.procInputDict = {}
                self.procInputDict['radarData'] = []
                elapsedTime = time.time() - startTime
            self.safeExit()
        except KeyboardInterrupt:
            self.safeExit()

    def safeExit(self):
        print('Stopping radar and camera threads')
        self.stopEvent.set()
        self.radarThread.join()
        print('Safe exit complete')
        sys.exit(0)

    def saveData(self):
        startTime = time.time()
        # print(f'deck length: {len(self.radarDataDeck)}')
        timeString = time.strftime(u"%Y%m%d-%H%M%S")
        with open(self.radar_data_dir +
                  timeString + '_' +
                  self.radar_file_name + '_.csv', 'w') as csvFile:
            csvWriter = csv.writer(csvFile)
            for rdDataRow in self.radarDataDeck:
                csvWriter.writerow(rdDataRow)
        self.radarDataDeck.clear()

       print ('Data saved...................')
        elapsedTime = time.time() - startTime
        print ('Elapsed %f ms' % (elapsedTime * 1000))

if __name__ == '__main__':
    mc = MainClass()
    mc.main()
