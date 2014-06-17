# this file is a modification of pulseOx.py and wil have the program keep looping forever, alternating between 
# collecting the red LED data, IR data and then transmitting it over the Serial to python to process and display
# on a graph. 
import serial, numpy, scipy.signal, time, math
import matplotlib.pyplot as plt

# variables and constants...
timeToBeScanned = 3		# time in seconds for which EACH wavelength shall be scanned
samplingFreq = 100.0	# number of samples per second of the acquisition in the teensy
scansRun = 0			# this will count the number of times a "scan" has been run, and accordingly update the plotted time axis

### function definitions...
def smooth(x,window_len=11,window='hanning'):
    """smooth the data using a window with requested size.
    
    This method is based on the convolution of a scaled window with the signal.
    The signal is prepared by introducing reflected copies of the signal 
    (with the window size) in both ends so that transient parts are minimized
    in the begining and end part of the output signal.
    
    input:
        x: the input signal 
        window_len: the dimension of the smoothing window; should be an odd integer
        window: the type of window from 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'
            flat window will produce a moving average smoothing.

    output:
        the smoothed signal
        
    example:

    t=linspace(-2,2,0.1)
    x=sin(t)+randn(len(t))*0.1
    y=smooth(x)
    
    see also: 
    
    numpy.hanning, numpy.hamming, numpy.bartlett, numpy.blackman, numpy.convolve
    scipy.signal.lfilter
 
    TODO: the window parameter could be the window itself if an array instead of a string
    NOTE: length(output) != length(input), to correct this: return y[(window_len/2-1):-(window_len/2)] instead of just y.
    """

    if x.ndim != 1:
        raise ValueError, "smooth only accepts 1 dimension arrays."

    if x.size < window_len:
        raise ValueError, "Input vector needs to be bigger than window size."


    if window_len<3:
        return x


    if not window in ['flat', 'hanning', 'hamming', 'bartlett', 'blackman']:
        raise ValueError, "Window is on of 'flat', 'hanning', 'hamming', 'bartlett', 'blackman'"


    s=numpy.r_[x[window_len-1:0:-1],x,x[-1:-window_len:-1]]
    #print(len(s))
    if window == 'flat': #moving average
        w=numpy.ones(window_len,'d')
    else:
        w=eval('numpy.'+window+'(window_len)')

    y=numpy.convolve(w/w.sum(),s,mode='valid')
    return y

# SETUP: open serial port, establish communication. open files for saving to (today's date and cardinal index
print("opening port..")
teensy = serial.Serial(3, 115200, timeout=1)		# open serial port, needs to be one less than what Arduino IDE shows (COMx)
print "port open"

### open file for saving to...
import time, os

count = 0
while os.path.exists("%s-%s.txt" % (time.strftime("%Y%m%d"), count)):
  count += 1
fh = open("%s-%s.txt" % (time.strftime("%Y%m%d"), count), "w")

# Tell the teensy to collect information (red/IR for a time period of 1s each..
print "sending acquire data command..."
teensy.write('c')
time.sleep(0.001)		# a very small delay to allow debouncing and crazy shit to stop, otherwise the program's skipping steps wtf

# enter while loop...
while(True):
  # re-initialize variables...
  # serialData = []
  redData = []
  redMinimas = []
  redMaximas = []
  
  irData = []
  irMaximas = []
  irMinimas = []

  # step 1: listen for the 'finished collecting' character on the serial monitor from the teensy...
  time.sleep(timeToBeScanned-1)
  char = teensy.readline().strip()
  # print(char)
  if (char == 'd'):
    print("teensy has finished the acquisition...")
    # now we can proceed with data collection...
	# send the teensy the message to send the data over serial...
    print "requesting data from teensy..."
    teensy.write('t')
  
    # step 2: collect the data real quick from the teensy over serial..
    for i in  range(0, int(samplingFreq*timeToBeScanned)):
      data = teensy.readline()
      # serialData.append(data)
      # print(str(i) + ": " + data)
	  # split that shit up into red and IR data at liesure
	
      z = (data.strip()).split('\t')		# split data at tab
      # print(z)
      # red = int(z[0])
      # print red
  
      # ir = int(z[1])
      redData.append(int(z[0]))			# append int version of the value into the datas list
      irData.append(int(z[1]))
	
      # print redData
      # print irData
	  
    print "data has been acquired, now processing begins..."
  
  # step 3: find maxima, minima for both red and IR. find difference as HR
  ### convert to numpy arrays...
  if (len(redData) == 0):
    print "data is in some messed up format"
  else:
    redData = numpy.array(redData)
    irData = numpy.array(irData)
  
    # we're also going to smooth these before making them numpy arrays.
    smoothWindow = 11		# make sure this is always an odd number
    plotCutoffs = int(smoothWindow/2)
    redDataSmoothed = smooth(numpy.array(redData), window_len=smoothWindow)[plotCutoffs:-plotCutoffs]
    irDataSmoothed = smooth(numpy.array(irData), window_len=smoothWindow)[plotCutoffs:-plotCutoffs]

    # REMEMBER THAT THE DATA IS int COMING FROM THE ADC
    # also remember that argrelextrema returns the indices of the extremas, not the extremas themselves
    ### finding the maximas...
    argrelOrder = 30				# set the order/window for maxima/minima peak finding
    redMaximas = scipy.signal.argrelmax(redDataSmoothed, order=argrelOrder)[0]
    irMaximas = scipy.signal.argrelmax(irDataSmoothed, order=argrelOrder)[0]

    ### finding the minimas...
    redMinimas = scipy.signal.argrelmin(redDataSmoothed, order=argrelOrder)[0]
    irMinimas = scipy.signal.argrelmin(irDataSmoothed, order=argrelOrder)[0]

    t = numpy.arange(len(redData))
	
    if len(redMaximas) > 1:
      hrMultiplier = 60.0*samplingFreq
      hr = hrMultiplier / (redMaximas[1] - redMaximas[0])
      print hr
	  print>>fh, hr		# print HR to the data file
      
    # step 4: calculate ratio of the AC peaks only ratio of (maxima-minima) for both wavelengths = o2sat  
    lcm = min(len(redMaximas), len(irMaximas), len(redMinimas), len(irMinimas))
    if lcm > 0:  
	  # only use numpy.log to calculate log and other mathematical operations on numpy arrays
      o2sat = (numpy.log((redMaximas[0] - redMinimas[0]).astype(float)) / numpy.log((irMaximas[0] - irMinimas[0]).astype(float))).mean()
      print "o2 sat is:"
      print o2sat
      print>>fh, o2sat	# print o2sat to the data file
    
    # step 5: append the PPG data to one file. append the HR and pulseOx to another file.
    # read out the HR and pulseOx on the command line/terminal.
	
    # step 6: plot the data that's come on now, but in such a way that the subsequent data will be added
    plt.ion() # set plot to animated  
	
    plt.clf()
    
	# leaving the first 10 points out because they are a "rise" feature whih prevents the smaller PPG signals from being seen...
	### RED data...
    '''
    line, = plt.plot(redData[10:], 'k--')
    line, = plt.plot(redDataSmoothed[10:], 'r')
    line, = plt.plot(t[redMaximas-10], redData[redMaximas], 'ko')
    line, = plt.plot(t[redMinimas-10], redData[redMinimas], 'bo')
    '''
	### IR data...
    
    line, = plt.plot(irData[10:], 'b--')
    line, = plt.plot(irDataSmoothed[10:], 'g')
    line, = plt.plot(t[irMaximas-10], irDataSmoothed[irMaximas], 'ko')
    line, = plt.plot(t[irMinimas-10], irDataSmoothed[irMinimas], 'bo')
    
    # line, = plt.plot(irData)
    
    # print numpy.arange(scansRun*samplingFreq, (scansRun+1)*samplingFreq)
    # print len(numpy.arange(scansRun*samplingFreq, (scansRun+1)*samplingFreq))
    # line.set_xdata(numpy.arange(scansRun*len(redData), (scansRun+1)*len(redData)))
	
    # line.set_xdata(numpy.append(line.get_xdata(), numpy.arange(scansRun*len(redData), (scansRun+1)*len(redData))))
    # line.set_ydata(numpy.append(line.get_ydata(), redData))  # update the data
    plt.draw() # update the plot

    scansRun += 1	# update the variable
    # print line.get_xdata()
  
  # REPEAT
  print "REPEAT sending acquire command"
  teensy.write('c')