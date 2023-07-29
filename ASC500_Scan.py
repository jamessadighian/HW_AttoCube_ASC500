# -*- coding: utf-8 -*-
"""
Created on Tue Apr 26 11:35:17 2022

@author: James Sadighian
"""

from ScopeFoundry import Measurement
from ScopeFoundry.helper_funcs import sibling_path, load_qt_ui_file
from PyQt5.QtWidgets import QMainWindow, QApplication, QFileDialog
from PyQt5.QtCore import QTimer
from PyQt5 import uic
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
import numpy as np
import time
import pyqtgraph as pg
from pyqtgraph.Qt import QtGui, QtCore, QtWidgets
from pyqtgraph.Point import Point
import os
import customplotting.mscope as cpm
import matplotlib.pyplot as plt
from TimeTagger import DelayedChannel, GatedChannel, TimeDifferences, Flim, createTimeTagger, freeTimeTagger

class ASC500_Scan(Measurement):
    
    # this is the name of the measurement that ScopeFoundry uses when displaying your measurement and saving data related to it
    name='ASC500_Scan'
    
    def setup(self):
        """
        Runs once during App initialization.
        This is the place to load a user interface file,
        define settings, and set up data structures. 
        """
        
        self.display_update_period = 0.1 #seconds
        
        #S = self.settings #create variable S, which is all the settings
        
        self.settings.New('x_range', dtype=float, unit='um')
        self.settings.New('y_range', dtype=float, unit='um')
        # S.New('x_pixels', dtype=int, ro=False, unit="um", vmin=1, vmax=50, initial=10)
        # S.New('y_pixels', dtype=int, ro=False, unit='um', vmin=1, vmax=50, initial=10)
        self.settings.New('x_pos', dtype=float, ro=False, unit="um", vmin=0, vmax=50)
        self.settings.New('y_pos', dtype=float, ro=False, unit='um', vmin=0, vmax=50)
        self.settings.New('x_clicked', dtype=float, initial=0, unit='um', vmin=0, vmax=100)#, ro=True)
        self.settings.New('y_clicked', dtype=float, initial=0, unit='um', vmin=0, vmax=100)#, ro=True)

        self.settings.New('lock_position', dtype=bool, initial=False)
        self.settings.New('save_positions', dtype=bool, initial=False)
        
        self.settings.New('fix_xy', dtype=bool, initial=True)

        
        # UI 
        self.ui_filename = sibling_path(__file__,"stage_scan2.ui")    #this whole section just loads the ui file
        self.ui = load_qt_ui_file(self.ui_filename)
        self.ui.setWindowTitle(self.name)
        self.ui.setWindowTitle('scan me harder FLIM daddy')

        self.elapsed_time = 0                               #creates a counter and empty data arrays
        #self.xdata = [] #array storing countrate data
        #self.ydata = [] #array storing time points
        
        self.asc500_hw = self.app.hardware['ASC500']
    
    def setup_figure(self):
        S = self.settings                           #creates instance of S within this function?
        #self.tt_hw = self.app.hardware['timetagger'] #creates instance of the timetagger hw in this function?
        
        
        #connect events/settings to ui
        #S.progress.connect_bidir_to_widget(self.ui.progressBar) #no need to connect this since its in daisy rn
        
        '''
        active connections on gui
        '''
        self.asc500_hw.settings.Columns.connect_to_widget(self.ui.x_step_doubleSpinBox)
        self.asc500_hw.settings.Lines.connect_to_widget(self.ui.y_step_doubleSpinBox)
        self.asc500_hw.settings.pixel_size.connect_bidir_to_widget(self.ui.PixelSize_doubleSpinBox)
        self.ui.start_scan_pushButton.clicked.connect(self.start)
        # self.ui.interrupt_scan_pushButton.clicked.connect(self.interrupt)
        self.ui.interrupt_scan_pushButton.clicked.connect(self.stopscanning)
        self.settings.fix_xy.connect_to_widget(self.ui.fix_xy_checkBox)
        # S.y_pixels.connect_bidir_to_widget(self.ui.num_ypixels_doubleSpinBox)
        # S.x_pixels.connect_bidir_to_widget(self.ui.num_xpixels_doubleSpinBox)
        self.settings.x_pos.connect_bidir_to_widget(self.ui.x_pos_doubleSpinBox)
        self.settings.y_pos.connect_bidir_to_widget(self.ui.y_pos_doubleSpinBox) 

        self.settings.x_range.connect_bidir_to_widget(self.ui.x_size_doubleSpinBox)   
        self.settings.y_range.connect_bidir_to_widget(self.ui.y_size_doubleSpinBox)
        '''matplotlib figure'''
        
        self.fig = Figure()
        self.flimAxis = self.fig.add_subplot(111)
        
        # self.fig, self.flim = Figure(figsize=(50,50))

        
        self.canvas = FigureCanvasQTAgg(self.fig)

        self.toolbar = NavigationToolbar2QT(self.canvas, parent = None) #self)
        self.ui.stage_groupBox.layout().addWidget(self.toolbar)
        self.ui.stage_groupBox.layout().addWidget(self.canvas)
        
        self.mylabelsize=8
        
        self.flimAxis.set_xlabel('pixels', fontsize=self.mylabelsize)
        self.flimAxis.set_xlim(0,self.asc500_hw.settings['Columns'])
        self.flimAxis.set_ylabel('pixels', fontsize=self.mylabelsize)
        self.flimAxis.set_ylim(0,self.asc500_hw.settings['Lines'])
        self.flimAxis.set_title('FLIM', fontsize=self.mylabelsize)
        self.flimAxis.tick_params(axis='both', labelsize=8)
        
        
        
        
        self.flimarray = np.zeros((int(self.asc500_hw.settings['Lines']), int(self.asc500_hw.settings['Columns'])))
        
        self.flimim = self.flimAxis.imshow(self.flimarray, cmap='gray', vmin=0, vmax=100, origin='lower')
        # self.counterline, = self.counterAxis.plot([],[])
        # self.counterline2, = self.counterAxis.plot([],[])
        
        self.fig.tight_layout()
        
        '''
        Runs once during App initialization, after setup()
        This is the place to make all graphical interface initializations,
        build plots, etc.
        
        20220906 commented getCounterNormalizationFactor so i can swap the counteraxis to correlation
        
        '''
    def run(self):
        '''
        Runs when measurement is started. Runs in a separate thread from GUI.
        It should not update the graphical interface directly, and should only
        focus on data acquisition.
        '''
        self.tt_hw = self.app.hardware['timetagger']                      

        
        # flim_n_pixels = self.settings['x_pixels'] * self.settings['y_pixels']
        
        # sleep_time = self.display_update_period
        
        # t0 = time.time()
        
        
        # integr_time=self.settings['int_time']
        # delayed_vch = DelayedChannel(self.tt_hw.tagger, 4, self.settings['int_time'])
        
        # PIXEL_END_CH = delayed_vch.getChannel()
        
        # gated_vch = GatedChannel(self.tt_hw.tagger, 2, 4, PIXEL_END_CH)
        # GATED_SPD_CH = gated_vch.getChannel()
        
        # self.flim = Flim(self.tt_hw.tagger, 
        #                   click_channel=GATED_SPD_CH,
        #                   start_channel=1,
        #                   next_channel=4,
        #                   binwidth=self.settings['flim_binwidth'],
        #                   n_bins=self.settings['flim_n_bins'],
        #                   n_histograms=flim_n_pixels
        #                 )

        # while not self.interrupt_measurement_called:
        #     time.sleep(.01)
        
        self.asc500_hw.asc500.scanner.startScanner()
        # if self.interrupt_measurement_called:
        #     self.asc500_hw.asc500.scanner.pauseScanner()
        #self.elasped_time = 0
        # while not self.interrupt_measurement_called:
        #     time.sleep(.01)
        # save_dict = {
        #              'time_histogram': countdata,
        #              'time_array': timedata
        #             }        
        
    def update_display(self):
        '''
        Displays (plots) the data
        This function runs repeatedly and automatically during the measurement run.
        its update frequency is defined by self.display_update_period
        '''
        # self.tt_hw = self.app.hardware['timetagger']
        # '''
        # beginning of cryostat FLIM plotting code
        # '''
        
        # temp = self.flim.getCurrentFrameIntensity()
        
        # #temp.shape = (temp.size//self.settings['x_pixels'], self.settings['x_pixels'])  #if this doesn't work i think ill just kill myself

        # b = np.reshape(temp, (-1, self.settings['x_pixels'])) #if the bullshit above doesn't work, we can try this
        
        # self.flimim.set_data(b)
        
        # self.flimim.set_clim(vmax=np.amax(b))
        
        # self.canvas.draw()
        # self.canvas.flush_events()  #james, check if this runs in background in scopefoundry as part of a measurement class
        
        
        #print('test1.6')
        
    def set_details_widget(self, widget = None, ui_filename=None):
        """ Helper function for setting up ui elements for settings. """
        #print('LOADING DETAIL UI')
        if ui_filename is not None:
            details_ui = load_qt_ui_file(ui_filename)
        if widget is not None:
            details_ui = widget
        if hasattr(self, 'details_ui'):
            if self.details_ui is not None:
                self.details_ui.deleteLater()
                self.ui.details_groupBox.layout().removeWidget(self.details_ui)
                #self.details_ui.hide()
                del self.details_ui
        self.details_ui = details_ui
        #return replace_widget_in_layout(self.ui.details_groupBox,details_ui)
        self.ui.details_groupBox.layout().addWidget(self.details_ui)
        return self.details_ui
    
    def save_flim_data(self):
        print('daddy im saving as hard as i can')
        
        temp = self.flim.getCurrentFrame()
        flim_data = temp.np.reshape(self.settings['x_pixels'], self.settings["y_pixels"], temp.shape[0])
        append = '_flim_data.npy' #string to append to sample name

        self.check_filename(append)
        
        np.save(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, flim_data, fmt='%f')

        # np.save(r"C:\Users\GingerCryostat\Desktop\flim.npy", flim_data, fmt='%f') 

        
        print('finished saving daddy')
    
    def getscannerpos(self, axis):
        pos=self.asc500_hw.asc500.scanner.getPositionsXYRel()
        return pos[axis]
        
        
    def clear_plot(self):
        self.flim.clear()
    
    def check_filename(self, append):
        '''
        If no sample name given or duplicate sample name given, fix the problem by appending a unique number.
        append - string to add to sample name (including file extension)
        '''
        samplename = self.app.settings['sample']
        filename = samplename + append
        directory = self.app.settings['save_dir']
        if samplename == "":
            self.app.settings['sample'] = int(time.time())
        if (os.path.exists(directory+"/"+filename)):
            self.app.settings['sample'] = samplename + str(int(time.time()))        
    
    def stopscanning(self):
        self.asc500_hw.asc500.scanner.pauseScanner()
        # self.asc500_hw.asc500.scanner.stopScanner()   #switch back to this once attocube fucking fixes it
        
    def save_intensities_data(self, intensities_array, hw_name):
        """
        intensities_array - array of intensities to save
        hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
        """
        append = '_' + hw_name + '_intensity_sums.npy' #string to append to sample name
        self.check_filename(append)
        #transposed = np.transpose(intensities_array)   in case we need to transpose this for whatever reason, just uncomment this Jess, then change the saved variable below from "transposed" to 
        np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, intensities_array, fmt='%f')

    def save_intensities_image(self, intensities_array, hw_name):
        """
        intensities_array - array of intensities to save as image
        hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
        """
        append = '_' + hw_name + '_intensity_sums.png'
        cpm.plot_confocal(intensities_array, stepsize=np.abs(self.settings['x_step']))
        self.check_filename(append)
        plt.savefig(self.app.settings['save_dir'] + '/' + self.app.settings['sample'] + append, bbox_inches='tight', dpi=300)
        
    def save_histogram_arrays(self, flim_array, time_array, hw_name):
        """
        data_array - 2D array of 1D arrays storing intensities
        time_array - 2D array of 1D arrays storing times
        hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
        """
        print('daddy im saving as hard as i can')
        append_flim = '_' + hw_name + '_intensity_arr.npy'
        append_time = '_' + hw_name + '_time_arr.npy'
        self.check_filename(append_flim)
        self.check_filename(append_time)
        np.save(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append_flim, flim_array)
        np.save(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append_time, time_array)








































# '''
#     pyqt figure
#     '''
#     #stage ui base
#     self.stage_layout=pg.GraphicsLayoutWidget()
#     self.ui.stage_groupBox.layout().addWidget(self.stage_layout)
#     self.stage_plot = self.stage_layout.addPlot(title="Stage view")
#     self.stage_plot.setXRange(0, 100)
#     self.stage_plot.setYRange(0, 100)
#     self.stage_plot.setLimits(xMin=0, xMax=100, yMin=0, yMax=100) 

#     #region of interest - allows user to select scan area
#     self.scan_roi = pg.ROI([0,0],[25, 25], movable=True)
#     self.handle1 = self.scan_roi.addScaleHandle([1, 1], [0, 0])
#     self.handle2 = self.scan_roi.addScaleHandle([0, 0], [1, 1])        
#     self.scan_roi.sigRegionChangeFinished.connect(self.mouse_update_scan_roi)
#     self.scan_roi.sigRegionChangeFinished.connect(self.update_ranges)
#     self.stage_plot.addItem(self.scan_roi)

#     #setup ui signals
#     self.ui.start_scan_pushButton.clicked.connect(self.start)
#     self.ui.interrupt_scan_pushButton.clicked.connect(self.interrupt)
#     # self.ui.move_to_selected_pushButton.clicked.connect(self.move_to_selected)
#     # self.ui.export_positions_pushButton.clicked.connect(self.export_positions)

#     # self.ui.x_start_doubleSpinBox.valueChanged.connect(self.update_roi_start)
#     # self.ui.y_start_doubleSpinBox.valueChanged.connect(self.update_roi_start)
#     # self.ui.x_size_doubleSpinBox.valueChanged.connect(self.update_roi_size)
#     # self.ui.y_size_doubleSpinBox.valueChanged.connect(self.update_roi_size)
#     # self.ui.x_step_doubleSpinBox.valueChanged.connect(self.update_roi_start)
#     # self.ui.y_step_doubleSpinBox.valueChanged.connect(self.update_roi_start)

#     # self.ui.x_size_doubleSpinBox.valueChanged.connect(self.update_ranges)
#     # self.ui.y_size_doubleSpinBox.valueChanged.connect(self.update_ranges)
#     # self.ui.x_step_doubleSpinBox.valueChanged.connect(self.update_ranges)
#     # self.ui.y_step_doubleSpinBox.valueChanged.connect(self.update_ranges)

#     #histogram for image
#     self.hist_lut = pg.HistogramLUTItem()
#     self.stage_layout.addItem(self.hist_lut)

#     #image on stage plot, will show intensity sums
#     self.img_item = pg.ImageItem()
#     self.stage_plot.addItem(self.img_item)
#     blank = np.zeros((3,3))
#     self.img_item.setImage(image=blank) #placeholder image
    
#     self.hist_lut.setImageItem(self.img_item) #setup histogram

#     #arrow showing stage location
#     self.current_stage_pos_arrow = pg.ArrowItem()
#     self.current_stage_pos_arrow.setZValue(100)
#     self.stage_plot.addItem(self.current_stage_pos_arrow)
#     # self.pi_device_hw.settings.x_position.updated_value.connect(self.update_arrow_pos, QtCore.Qt.UniqueConnection)
#     # self.pi_device_hw.settings.y_position.updated_value.connect(self.update_arrow_pos, QtCore.Qt.UniqueConnection)

#     #Define crosshairs that will show up after scan, event handling.
#     self.vLine = pg.InfiniteLine(angle=90, movable=False, pen='r')
#     self.hLine = pg.InfiniteLine(angle=0, movable=False, pen='r')
#     self.stage_plot.scene().sigMouseClicked.connect(self.ch_click)

# def ch_click(self, event):
#     '''
#     Handle crosshair clicking, which toggles movement on and off.
#     '''
#     pos = event.scenePos()
#     if not self.settings['lock_position'] and self.stage_plot.sceneBoundingRect().contains(pos):
#         mousePoint = self.stage_plot.vb.mapSceneToView(pos)
#         self.vLine.setPos(mousePoint.x())
#         self.hLine.setPos(mousePoint.y())
#         self.settings['x_clicked'] = mousePoint.x()
#         self.settings['y_clicked'] = mousePoint.y()
#         if self.settings['save_positions']:
#             self.selected_positions[self.selected_count, 0] = mousePoint.x()
#             self.selected_positions[self.selected_count, 1] = mousePoint.y()
#             self.selected_count += 1

# def export_positions(self):
#     """ Export selected positions into txt. """
#     self.check_filename("_selected_positions.txt")
#     trimmed = self.selected_positions[~np.all(self.selected_positions == 0, axis=1)] #get rid of empty rows
#     np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + "_selected_positions.txt", trimmed, fmt='%f')

# def move_to_selected(self):
#     """Move stage to position selected by crosshairs."""
#     if self.scan_complete and hasattr(self, 'pi_device'):
#         x = self.settings['x_clicked']
#         y = self.settings['y_clicked']
#         self.pi_device.MOV(axes=self.axes, values=[x, y])
#         self.pi_device_hw.read_from_hardware()

# def mouse_update_scan_roi(self):
#     """Update settings and spinboxes to reflect region of interest."""
#     x0,y0 =  self.scan_roi.pos()
#     w, h =  self.scan_roi.size()
#     if self.settings['x_step'] > 0: 
#         self.settings['x_start'] = x0
#     else: 
#         self.settings['x_start'] = x0 + w

#     if self.settings['y_step'] > 0:
#         self.settings['y_start'] = y0
#     else:
#         self.settings['y_start'] = y0 + h 

#     self.settings['x_size'] = w
#     self.settings['y_size'] = h

# def update_roi_start(self):
#     """Update region of interest start position according to spinboxes"""
#     x_roi = self.settings['x_start'] #default start values that work with positive x and y steps
#     y_roi = self.settings['y_start']
#     if self.settings['x_step'] < 0:
#         x_roi = self.settings['x_start'] - self.settings['x_size']
#     if self.settings['y_step'] < 0:
#         y_roi = self.settings['y_start'] - self.settings['y_size']
#     self.scan_roi.setPos(x_roi, y_roi)

# def update_roi_size(self):
#     ''' Update region of interest size according to spinboxes '''
#     self.scan_roi.setSize((self.settings['x_size'], self.settings['y_size']))

# def update_ranges(self):
#     """ 
#     Update # of pixels calculation (x_range and y_range) when spinboxes change
#     This is important in getting estimated scan time before scan starts.
#     """
#     self.x_scan_size = self.settings['x_size']
#     self.y_scan_size = self.settings['y_size']
    
#     self.x_step = self.settings['x_step']
#     self.y_step = self.settings['y_step']

#     if self.y_scan_size == 0:
#         self.y_scan_size = 1
#         self.y_step = 1
    
#     if self.x_scan_size == 0:
#         self.x_scan_size = 1
#         self.x_step = 1
    
#     if self.y_step == 0:
#         self.y_step = 1
        
#     if self.x_step == 0:
#         self.x_step = 1

#     self.x_range = np.abs(int(np.ceil(self.x_scan_size/self.x_step)))
#     self.y_range = np.abs(int(np.ceil(self.y_scan_size/self.y_step)))
#     self.update_estimated_scan_time()

# def update_estimated_scan_time(self):
#     """implemented in hard-specific scan programs"""
#     pass

# def update_arrow_pos(self):
#     '''
#     Update arrow position on image to stage position
#     '''
#     x = self.pi_device_hw.settings['x_position']
#     y = self.pi_device_hw.settings['y_position']
#     self.current_stage_pos_arrow.setPos(x,y)

# def pre_run(self):
#     """
#     Define devices, scan parameters, and move stage to start.
#     """
#     self.pi_device = self.pi_device_hw.pi_device
#     self.axes = self.pi_device_hw.axes

#     #disable roi and spinboxes during scan
#     self.scan_roi.removeHandle(self.handle1)
#     self.scan_roi.removeHandle(self.handle2)
#     self.scan_roi.translatable = False
#     for lqname in "scan_direction x_start y_start x_size y_size x_step y_step".split():
#         self.settings.as_dict()[lqname].change_readonly(True)

#     self.x_start = self.settings['x_start']
#     self.y_start = self.settings['y_start']

#     self.pi_device.MOV(axes=self.axes, values=[self.x_start, self.y_start])
#     self.pi_device_hw.read_from_hardware()

# def update_display(self):
#     """
#     Displays (plots) the numpy array self.buffer. 
#     This function runs repeatedly and automatically during the measurement run.
#     its update frequency is defined by self.display_update_period
#     """
#     self.pi_device_hw.read_from_hardware()
#     roi_pos = self.scan_roi.pos()
#     self.img_item_rect = QtCore.QRectF(roi_pos[0], roi_pos[1], self.settings['x_size'], self.settings['y_size'])
#     self.img_item.setRect(self.img_item_rect)

#     if self.scan_complete:
#         self.ui.estimated_time_label.setText("Estimated time remaining: 0s")
#         self.ui.progressBar.setValue(100)
#         self.set_progress(100)
#         self.stage_plot.addItem(self.hLine)
#         self.stage_plot.addItem(self.vLine)

#         x, y = self.scan_roi.pos()
#         middle_x = x + self.settings['x_size']/2
#         middle_y = y + self.settings['y_size']/2
#         self.hLine.setPos(middle_y)
#         self.vLine.setPos(middle_x)

# def run(self):
#     self.scan_complete = False
#     self.pixels_scanned = 0 #keep track of scan/'pixel' number
#     print("before if")
#     print("before for loop x_step: {}".format(self.x_step))
#     if (self.settings['scan_direction'] == 'XY'): #xy scan
#         print("inside if, before loop")
#         print("y_range: {}".format(self.y_range))
#         for i in range(0, self.y_range):
#             print("inside for loop")
#             print("y_range: {}".format(self.y_range))
#             print(self.pixels_scanned) # testing
#             print("x_range: {}".format(self.x_range))
#             for j in range(0, self.x_range):
#                 print("inside inner for loop")
#                 print(self.pixels_scanned)
#                 if self.interrupt_measurement_called:
#                     break
#                 #make sure the right indices of image arrays are updated
#                 self.index_x = j
#                 self.index_y = i
#                 print("inside for loop x_step: {}".format(self.x_step))
#                 if self.x_step < 0:
#                     self.index_x = self.x_range - j - 1
#                 if self.y_step < 0:
#                     self.index_y = self.y_range - i - 1
#                 print("before scan_measure y_range: {}".format(self.y_range))
#                 self.scan_measure() #defined in hardware-specific scans
#                 print("after scan_measure y_range: {}".format(self.y_range))
#                 self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
#                 print("after MVR y_range: {}".format(self.y_range))
#                 self.pixels_scanned+=1
#             # TODO
#             # if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
#             if i == self.y_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
#                 self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
#             else:                
#                 self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
#                 self.pi_device.MOV(axes=self.axes[0], values=[self.x_start])
#             if self.interrupt_measurement_called:
#                 break
#         print("exit nested for loops")
#         print(self.pixels_scanned)
#     elif (self.settings['scan_direction'] == 'YX'): #yx scan
#         print("inside elif branch")
#         for i in range(self.x_range):
#             print("inside second for loop")
#             for j in range(self.y_range):
#                 print("inside second inner for loop")
#                 if self.interrupt_measurement_called:
#                     break

#                 #make sure the right indices of image arrays are updated
#                 self.index_x = i
#                 self.index_y = j
#                 if self.x_step < 0:
#                     self.index_x = self.x_range - i - 1
#                 if self.y_step < 0:
#                     self.index_y = self.y_range - j - 1
#                 self.scan_measure()
#                 self.pi_device.MVR(axes=self.axes[1], values=[self.y_step])
#                 self.pixels_scanned+=1
#             # TODO
#             # if statement needs to be modified to keep the stage at the finish y-pos for line scans in x, and same for y
#             if i == self.x_range-1: # this if statement is there to keep the stage at the finish position (in x) and not bring it back like we were doing during the scan 
#                 self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
#             else:                
#                 self.pi_device.MVR(axes=self.axes[0], values=[self.x_step])
#                 self.pi_device.MOV(axes=self.axes[1], values=[self.y_start])
#             if self.interrupt_measurement_called:
#                 break
#             print("exit elif branch")
#     self.scan_complete = True
#     print("scan complete")
#     print(self.pixels_scanned)
    
# def post_run(self):
#     """Re-enable roi and spinboxes. """
#     self.handle1 = self.scan_roi.addScaleHandle([1, 1], [0, 0])
#     self.handle2 = self.scan_roi.addScaleHandle([0, 0], [1, 1])
#     self.scan_roi.translatable = True
#     for lqname in "scan_direction x_start y_start x_size y_size x_step y_step".split():
#         self.settings.as_dict()[lqname].change_readonly(False)
        
# def scan_measure(self):
#     """
#     Not defined in this class. This is defined in hardware-specific scans that inherit this class.
#     """
#     pass

# def check_filename(self, append):
#     """
#     If no sample name given or duplicate sample name given, fix the problem by appending a unique number.
#     append - string to add to sample name (including file extension)
#     """
#     samplename = self.app.settings['sample']
#     filename = samplename + append
#     directory = self.app.settings['save_dir']
#     if samplename == "":
#         self.app.settings['sample'] = int(time.time())
#     if (os.path.exists(directory+"/"+filename)):
#         self.app.settings['sample'] = samplename + str(int(time.time()))

# def set_details_widget(self, widget = None, ui_filename=None):
#     """ Helper function for setting up ui elements for settings. """
#     #print('LOADING DETAIL UI')
#     if ui_filename is not None:
#         details_ui = load_qt_ui_file(ui_filename)
#     if widget is not None:
#         details_ui = widget
#     if hasattr(self, 'details_ui'):
#         if self.details_ui is not None:
#             self.details_ui.deleteLater()
#             self.ui.details_groupBox.layout().removeWidget(self.details_ui)
#             #self.details_ui.hide()
#             del self.details_ui
#     self.details_ui = details_ui
#     #return replace_widget_in_layout(self.ui.details_groupBox,details_ui)
#     self.ui.details_groupBox.layout().addWidget(self.details_ui)
#     return self.details_ui

# def save_intensities_data(self, intensities_array, hw_name):
#     """
#     intensities_array - array of intensities to save
#     hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
#     """
#     append = '_' + hw_name + '_intensity_sums.txt' #string to append to sample name
#     self.check_filename(append)
#     transposed = np.transpose(intensities_array)
#     np.savetxt(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append, transposed, fmt='%f')

# def save_intensities_image(self, intensities_array, hw_name):
#     """
#     intensities_array - array of intensities to save as image
#     hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
#     """
#     append = '_' + hw_name + '_intensity_sums.png'
#     cpm.plot_confocal(intensities_array, stepsize=np.abs(self.settings['x_step']))
#     self.check_filename(append)
#     plt.savefig(self.app.settings['save_dir'] + '/' + self.app.settings['sample'] + append, bbox_inches='tight', dpi=300)
    
# def save_histogram_arrays(self, data_array, time_array, hw_name):
#     """
#     data_array - 2D array of 1D arrays storing intensities
#     time_array - 2D array of 1D arrays storing times
#     hw_name - string that describes intensities source (ie. oo for oceanoptics, ph for picoharp) 
#     """
#     append_data = '_' + hw_name + '_intensity_arr.npy'
#     append_time = '_' + hw_name + '_time_arr.npy'
#     self.check_filename(append_data)
#     self.check_filename(append_time)
#     np.save(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append_data, data_array)
#     np.save(self.app.settings['save_dir']+"/"+ self.app.settings['sample'] + append_time, time_array)
