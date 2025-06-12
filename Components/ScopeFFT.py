import os
import sys

srcpath = os.path.realpath('.\SourceFiles')
sys.path.append(srcpath)
import warnings # this is for GUI warnings
warnings.filterwarnings("ignore")

from tevisainst import TEVisaInst

import numpy as np

import matplotlib.pyplot as plt
from matplotlib.widgets import Button

import keyboard
import time

#init DAC
#Set rates for DAC 
sampleRateDAC = 1.1E9

ncoFreq= 5.7E9

data_type = np.uint16

# Init ADC

breakVal = 0
dcOff = 0
spectrumInv = 0

#Set rates for ADC

sampleRateADC = 5E9
#sampleRateADC = 2.7E9

#Set number of frames to be collected
numframes, framelen = 1, 20*4800
totlen = numframes * framelen

#Preallocate processing memory
wav1 = np.zeros(framelen, dtype=np.uint16)
xT = np.linspace(0, numframes * framelen,  numframes * framelen )
xT = xT/sampleRateADC
tpCount = len(wav1)
timeStep = xT[1]-xT[0]
xF = np.fft.fftfreq(tpCount, timeStep)
xF = xF[range(int(len(wav1)/2))]


'''
# Connect to instrument(PXI)
sid = 12 #PXI slot of AWT on chassis
from teproteus import TEProteusAdmin as TepAdmin
admin = TepAdmin() #required to control PXI module
inst = admin.open_instrument(slot_id=sid) 
resp = inst.send_scpi_query("*IDN?") # Get the instrument's *IDN
print('connected to: ' + resp) # Print *IDN
'''
# Connect to instrument(LAN)
inst_addr = '169.254.18.140' #Proteus Lan
inst = TEVisaInst(inst_addr)

resp = inst.send_scpi_query("*IDN?")
print('connected to: ' + resp)
#inst.send_scpi_cmd(':INST:ACT:SEL 2')  
# initialize DAC
#inst.send_scpi_cmd('*CLS; *RST')        
    
# GUI - Button actions
  
def vMax(val):
    global inst
    cmd = ':DIG:CHAN:RANG HIGH'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:CHAN:RANG?')
    print('Range ' + range)
    
def vMed(val):
    cmd = ':DIG:CHAN:RANG MED'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:CHAN:RANG?')
    print('Range ' + range)

def vMin(val):
    cmd = ':DIG:CHAN:RANG LOW'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:CHAN:RANG?')
    print('Range ' + range)
    
def freeRun(val):
    cmd = ':DIG:TRIG:SOURCE CPU'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:TRIG:SOURCE?')
    print('Trigger ' + range)
    
def trigExt(val):
    cmd = ':DIG:TRIG:SOURCE TASK1'
    inst.send_scpi_cmd(cmd)
    range = inst.send_scpi_query(':DIG:TRIG:SOURCE?')
    print('Trigger ' + range)    
 
def exitLoop(val):
    global breakVal
    breakVal = 1
    
# Start the digitizer

 # initialize DAC and take the first capture.
inst.send_scpi_cmd(':DIG:MODE SING')

print('ADC Clk Freq {0}'.format(sampleRateADC))
cmd = ':DIG:FREQ  {0}'.format(sampleRateADC)
inst.send_scpi_cmd(cmd)

# Enable capturing data from channel 1
inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
inst.send_scpi_cmd(':DIG:CHAN:STATE ENAB')
# Select the internal-trigger as start-capturing trigger:
inst.send_scpi_cmd(':DIG:TRIG:SOURCE CPU')

cmd = ':DIG:ACQuire:FRAM:DEF {0},{1}'.format(numframes, framelen)
inst.send_scpi_cmd(cmd)

# Select the frames for the capturing 
# (all the four frames in this example)
capture_first, capture_count = 1, numframes
cmd = ':DIG:ACQuire:FRAM:CAPT {0},{1}'.format(capture_first, capture_count)
inst.send_scpi_cmd(cmd)

# Start the digitizer's capturing machine
inst.send_scpi_cmd(':DIG:INIT ON')
inst.send_scpi_cmd(':DIG:TRIG:IMM')
inst.send_scpi_cmd(':DIG:INIT OFF')

# Choose which frames to read (all in this example)
inst.send_scpi_cmd(':DIG:DATA:SEL ALL')

# Choose what to read 
# (only the frame-data without the header in this example)
inst.send_scpi_cmd(':DIG:DATA:TYPE FRAM')

# Get the total data size (in bytes)
resp = inst.send_scpi_query(':DIG:DATA:SIZE?')
num_bytes = np.uint32(resp)
print('Total read size in bytes: ' + resp)
print()

# Read the data that was captured by channel 1:
inst.send_scpi_cmd(':DIG:CHAN:SEL 1')
wavlen = num_bytes // 2
rc = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)

fourierTransform = np.fft.fft(wav1-dcOff)/len(wav1)           # Normalize amplitude
fourierTransform = abs(fourierTransform[range(int(len(wav1)/2))]) # Exclude sampling frequency

if(spectrumInv == 1):
    fftPlot = np.log10(fourierTransform[::-1])
else:
    fftPlot = np.log10(fourierTransform)
    

# GUI - Define the GUI

# Run GUI event loop
plt.ion()
  
# Create sub plots
figure, ax1 = plt.subplots(2)
line1, = ax1[0].plot(xT, wav1, color="yellow")
#line2, = ax1[1].plot(xF[80000:100000], fftPlot[80000:100000], color="yellow")
line2, = ax1[1].plot(xF, fftPlot, color="yellow")

# setting x-axis label and y-axis label
ax1[0].set(xlabel='Time = (Pts/'+ str(sampleRateDAC)+')', ylabel='Amplitude = (ADCRng/4096)')
ax1[0].set_position([0.2, 0.55, 0.7, 0.35]) #x, y, w, h]
ax1[0].set_ylim([0,4096])
ax1[0].set(facecolor = "black")
ax1[0].grid()

ax1[1].set(xlabel='Frequency', ylabel='FFT Amplitude')
ax1[1].set_position([0.2, 0.1, 0.7, 0.35]) #x, y, w, h]
#ax1[1].set_ylim([-3,2])
#ax1[1].set_xlim([0,60e6])
ax1[1].set(facecolor = "black")
ax1[1].grid()



xAnchor = 0.04
yAnchor = 0.33

ax1_button_500 = plt.axes([xAnchor, 0.85 , 0.03,0.05]) #xposition, yposition, width and height
grid_button_500 = Button(ax1_button_500, 'Max', color = 'white', hovercolor = 'grey')
grid_button_500.on_clicked(vMax)

ax1_button_800 = plt.axes([xAnchor+0.035, 0.85 , 0.03,0.05]) #xposition, yposition, width and height
grid_button_800 = Button(ax1_button_800, 'Med', color = 'white', hovercolor = 'grey')
grid_button_800.on_clicked(vMed)

ax1_button_1000 = plt.axes([xAnchor+(0.035*2), 0.85 , 0.03,0.05]) #xposition, yposition, width and height
grid_button_1000 = Button(ax1_button_1000, 'Min', color = 'white', hovercolor = 'grey')
grid_button_1000.on_clicked(vMin)


yAnchor = 0.7
# ax3_button_free = plt.axes([0.04, yAnchor , 0.1,0.05]) #xposition, yposition, width and height
# grid_button_free = Button(ax3_button_free, 'Free Run', color = 'white', hovercolor = 'grey')
# grid_button_free.on_clicked(freeRun)

# ax3_button_trig = plt.axes([0.04, yAnchor-0.075 , 0.1,0.05]) #xposition, yposition, width and height
# grid_button_trig = Button(ax3_button_trig, 'Trigger', color = 'white', hovercolor = 'grey')
# grid_button_trig.on_clicked(trigExt)

ax3_button_exit = plt.axes([0.04, yAnchor-(0.075*3) , 0.1,0.05]) #xposition, yposition, width and height
grid_button_exit = Button(ax3_button_exit, 'Exit', color = 'white', hovercolor = 'grey')
grid_button_exit.on_clicked(exitLoop)

    
def acquireData():
    wav1 = np.zeros(framelen, dtype=np.uint16)
    
    # Start the digitizer's capturing machine
    inst.send_scpi_cmd(':DIG:INIT ON')
    inst.send_scpi_cmd(':DIG:TRIG:IMM')
    # Stop the digitizer's capturing machine (to be on the safe side)
    inst.send_scpi_cmd(':DIG:INIT OFF')

    # Read the data that was captured by channel 1:
    inst.send_scpi_cmd(':DIG:CHAN:SEL 1')

    resp = inst.read_binary_data(':DIG:DATA:READ?', wav1, num_bytes)
    resp = resp
    #print("Aquisition Error = ")
    #print(resp)
    
    
    wav1 = wav1 - dcOff
    wav2 = wav1 - np.average(wav1)
    w = np.blackman(len(wav1))
    wavFFT = w * wav2    #wavFFT = wav1
    fourierTransform = np.fft.fft(wavFFT)/len(wav2)           # Normalize amplitude
    fourierTransform = abs(fourierTransform[range(int(len(wav2)/2))]) # Exclude sampling frequency

    if(spectrumInv == 1):
        fftPlot = np.log10(fourierTransform[::-1])
    else:
        fftPlot = np.log10(fourierTransform)

    # Plot the samples
    # updating data values
    line1.set_xdata(xT)
    line1.set_ydata(wav1) #Subtracting offset twice? 
    #line2.set_xdata(xF[80000:100000])
    #line2.set_ydata(fftPlot[80000:100000])
    
    line2.set_xdata(xF)
    line2.set_ydata(fftPlot)
    
    # drawing updated values
    figure.canvas.draw()
  
    # This will run the GUI event
    # loop until all UI events
    # currently waiting have been processed
    figure.canvas.flush_events()
     
    time.sleep(0.1)
    del wav1
    del fftPlot


# -------- IQ Mod ----------

#makeDCData(2048)
#downLoad_IQ_DUC()
#downLoad_mrkr()
#setTaskDUC()

cmd = ':OUTP ON'
rc = inst.send_scpi_cmd(cmd)



while True:
    try:
        if keyboard.is_pressed(' '):
            print("Stop initiated...")
            break
        if(breakVal==1):
            print("Stop initiated...")
            break
    
        acquireData()    
        
    except:
        break

inst.close_instrument()
