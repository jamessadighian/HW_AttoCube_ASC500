# -*- coding: utf-8 -*-
"""
Created on Thu Apr 21 12:49:03 2022

@author: James Sadighian
"""
import sys
import os
from ScopeFoundry import HardwareComponent
import time

try:
    asc500path=r"C:\Users\James Sadighian\Desktop\ASC500_Python_Control-master"
    sys.path.insert(0, asc500path)
    from lib import ASC500
except Exception as err:
    print('Could not load modules needed for AttoCube ASC500: {}'.format(err))

class ASC500HW(HardwareComponent):
    
#    name = 'asc500'

    def setup(self):

        
        self.name = 'ASC500'
        self.asc500=0

        
        # Define your hardware settings here.
        # These settings will be displayed in the GUI and auto-saved with data files

        self.settings.New('Columns', dtype=float, vmin=1, vmax=500, initial=20)
        self.settings.New('Lines', dtype=float, vmin=1, vmax=500, initial=20)
        self.settings.New('pixel_size', dtype=float, unit='m', si=True, spinbox_decimals=3, vmin=1e-11, vmax=50e-6, spinbox_step=1e-9, initial=1e-6)
        self.settings.New('sampTime', dtype=float, si=True, unit='s', spinbox_decimals=3, vmin=12.5e-3, vmax=3600, initial=1)

        
        
        
    def connect(self):
        binPath = asc500path+os.sep+"Installer\ASC500CL-V2.7.13" +os.sep
        dllPath = asc500path+os.sep+"64bit_lib\ASC500CL-LIB-WIN64-V2.7.13\daisybase\lib" +os.sep
        
        self.asc500 = ASC500(binPath, dllPath)
        self.asc500.base.startServer()
        self.asc500.base.sendProfile(r"C:\Users\GingerCryostat\Desktop\ASC500\01 ASC500 Installer and Data\ASC500CL-V2.7.14\Profile installation test\profile test.ngp")
        time.sleep(1)
        self.asc500.scanner.configureScanner(
            .000025, 
            .000025, 
            self.settings['pixel_size'], 
            self.settings['Columns'], 
            self.settings['Lines'], 
            #self.settings['sampTime'],
            2
            )  #something is definitely fucked up with the configureScanner function. if you try to set the pixel size to be 1e-6 meters (1 um) it sets it to 1 pm. I think someone at AttoCube fucked up the code.
        self.asc500.scanner.setSamplingTime(1) #have to put this here because for some reason if i don't it defaults the integration time to be 160 ms no matter what
        self.asc500.scanner.setPixelSize(1e-6)
        # self.settings.x_range.connect_to_hardware(
        #     read_func=self.getXRange,
        #     # write_func=self.setXRang
        #     )
        
        # self.settings.y_range.connect_to_hardware(
        #     read_func=self.getYRange,
        #     # write_func=self.setYRange
        #     )
        
        self.settings.Columns.connect_to_hardware(
            read_func=self.asc500.scanner.getNumberOfColumns,
            write_func=self.asc500.scanner.setNumberOfColumns
            )
        
        self.settings.Lines.connect_to_hardware(
            read_func=self.asc500.scanner.getNumberOfLines,
            write_func=self.asc500.scanner.setNumberOfLines
            )
        
        self.settings.pixel_size.connect_to_hardware(
            read_func=self.asc500.scanner.getPixelSize,
            write_func=self.asc500.scanner.setPixelSize
            )
        
        self.settings.sampTime.connect_to_hardware(
            read_func=self.asc500.scanner.getSamplingTime,
            write_func=self.asc500.scanner.setSamplingTime
            )
        
        self.asc500.scanner.setXEqualY(1)
        xequaly = self.asc500.scanner.getXEqualY()
        if xequaly == 1:
            print("x is equal to y daddy")
        else:
            print('uWu daddy i made a fucky wucky')
        
        #Take an initial sample of the data.
        self.read_from_hardware()
        
        
    def disconnect(self):
        #Disconnect the device and remove connections from settings
        print('abc')
        self.settings.disconnect_all_from_hardware()    #james can you find this in the scopefoundry code...is this necessary????
        if hasattr(self, 'ASC500'):
            print('def')
            #disconnect hardware
            #clean up hardware object
            self.asc500.base.stopServer()
            del self.asc500
            self.asc500 = None
    
    def getXRange(self):
        return self.settings['pixel_size']*self.settings['Columns']
               
    def getYRange(self):
        return self.settings['pixel_size']*self.settings['Lines']
    
    # def setXRange:
    #     self.settings
    # def setYRange:
        


