import bitstring
import pygatt
import numpy as np
from time import time, sleep
from sys import platform


class Muse():
    """Muse 2016 headband"""

    def __init__(self, address=None, callback=None,acc_data=None,gyro_data=None, eeg=True, accelero=False,
                 giro=False, backend='auto', interface=None, time_func=time,
                 name=None):
        """Initialize"""
        self.address = address
        self.name = name
        self.callback = callback
        self.acc_data = acc_data    #Data Accelerometer
        self.gyro_data = gyro_data  #Data Gyro
        self.eeg = eeg
        self.accelero = accelero
        self.giro = giro
        self.interface = interface
        self.time_func = time_func

        if backend in ['auto', 'gatt', 'bgapi']:
            if backend == 'auto':
                if platform == "linux" or platform == "linux2":
                    self.backend = 'gatt'
                else:
                    self.backend = 'bgapi'
            else:
                self.backend = backend
        else:
            raise(ValueError('Backend must be auto, gatt or bgapi'))

    def connect(self, interface=None, backend='auto'):
        """Connect to the device"""

        if self.backend == 'gatt':
            self.interface = self.interface or 'hci0'
            self.adapter = pygatt.GATTToolBackend(self.interface)
        else:
            self.adapter = pygatt.BGAPIBackend(serial_port=self.interface)

        self.adapter.start()

        if self.address is None:
            address = self.find_muse_address(self.name)
            if address is None:
                raise(ValueError("Can't find Muse Device"))
            else:
                self.address = address
        self.device = self.adapter.connect(self.address)

        # subscribes to EEG stream
        if self.eeg:
            self._subscribe_eeg()

        # subscribes to Accelerometer
        if self.accelero:
            self._subscribe_acc()
            #raise(NotImplementedError('Accelerometer not implemented'))

        # subscribes to Giroscope
        if self.giro:
            self._subscribe_gyro()
            #raise(NotImplementedError('Giroscope not implemented'))

    def find_muse_address(self, name=None):
        """look for ble device with a muse in the name"""
        list_devices = self.adapter.scan(timeout=10.5)
        for device in list_devices:
            if name:
                if device['name'] == name:
                    print('Found device %s : %s' % (device['name'],
                                                    device['address']))
                    return device['address']

            elif 'Muse' in device['name']:
                    print('Found device %s : %s' % (device['name'],
                                                    device['address']))
                    return device['address']

        return None

    def start(self):
        """Start streaming."""
        self._init_timestamp_correction()
        self._init_sample()
        self.last_tm = 0
        self.device.char_write_handle(0x000e, [0x02, 0x64, 0x0a], False)

    def stop(self):
        """Stop streaming."""
        self.device.char_write_handle(0x000e, [0x02, 0x68, 0x0a], False)

    def disconnect(self):
        """disconnect."""
        self.device.disconnect()
        self.adapter.stop()

    def _subscribe_eeg(self):
        """subscribe to eeg stream."""
        self.device.subscribe('273e0003-4c4d-454d-96be-f03bac821358',
                              callback=self._handle_eeg)
        self.device.subscribe('273e0004-4c4d-454d-96be-f03bac821358',
                              callback=self._handle_eeg)
        self.device.subscribe('273e0005-4c4d-454d-96be-f03bac821358',
                              callback=self._handle_eeg)
        self.device.subscribe('273e0006-4c4d-454d-96be-f03bac821358',
                              callback=self._handle_eeg)
        self.device.subscribe('273e0007-4c4d-454d-96be-f03bac821358',
                              callback=self._handle_eeg)

    #NEW
    def _subscribe_acc(self):
		self.device.subscribe('273e000a-4c4d-454d-96be-f03bac821358',
							  callback=self._handle_acc)
							  
    def _subscribe_gyro(self):
		self.device.subscribe('273e0009-4c4d-454d-96be-f03bac821358',
							  callback=self._handle_gyro)
    
    
    def _unpack_acc_channel(self,packet):
        
        #Unpack 10 data		???
		a = bitstring.Bits(bytes=packet)
		pattern = "uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16"
		res = a.unpack(pattern) # Transforma los datos en 16bit 
		return res
		
    def _unpack_gyro_channel(self,packet):
		#Unpack 10 Data    ???
		a = bitstring.Bits(bytes=packet)
		pattern = "uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16,uint:16"
		res = a.unpack(pattern) # Transforma los datos en 16bit
		return res
    #NEW
    
    def _unpack_eeg_channel(self, packet):
        """Decode data packet of one EEG channel.

        Each packet is encoded with a 16bit timestamp followed by 12 time
        samples with a 12 bit resolution.
        """
        aa = bitstring.Bits(bytes=packet)
        pattern = "uint:16,uint:12,uint:12,uint:12,uint:12,uint:12,uint:12, \
                   uint:12,uint:12,uint:12,uint:12,uint:12,uint:12"
        res = aa.unpack(pattern)
        packetIndex = res[0]
        data = res[1:]
        # 12 bits on a 2 mVpp range
        data = 0.48828125 * (np.array(data) - 2048)
        return packetIndex, data

    def _init_sample(self):
        """initialize array to store the samples"""
        self.timestamps = np.zeros(5)
        self.data = np.zeros((5, 12))

    def _init_timestamp_correction(self):
        """Init IRLS params"""
        # initial params for the timestamp correction
        # the time it started + the inverse of sampling rate
        self.sample_index = 0
        self.reg_params = np.array([self.time_func(), 1./256])

    def _update_timestamp_correction(self, x, y):
        """Update regression for dejittering

        use stochastic gradient descent
        """
        pass

   # return data
   def _handle_acc(self, handle, data):
		#print handle,data
		if handle == 23:
			d_acc = self._unpack_acc_channel(data)
            """average"""
			self.acc_x = (d_acc[1]+d_acc[4]+d_acc[7])/3
			self.acc_y = (d_acc[2]+d_acc[5]+d_acc[8])/3
			self.acc_z = (d_acc[3]+d_acc[6]+d_acc[9])/3
			#return self.acc_x
			self.acc_data(self.acc_x,self.acc_y,self.acc_z)
			
    def _handle_gyro(self, handle, data):
		#print handle,data
        
		if handle == 20:
			d_gyro = self._unpack_gyro_channel(data)
			"""average"""
            
            self.gyro_x = (d_gyro[1]+d_gyro[4]+d_gyro[7])/3
			self.gyro_y = (d_gyro[2]+d_gyro[5]+d_gyro[8])/3
			self.gyro_z = (d_gyro[3]+d_gyro[6]+d_gyro[9])/3
			
			self.gyro_data(self.gyro_x,self.gyro_y,self.gyro_z)
			
    
    
    def _handle_eeg(self, handle, data):
        """Callback for receiving a sample.

        sample are received in this oder : 44, 41, 38, 32, 35
        wait until we get 35 and call the data callback
        """
        timestamp = self.time_func()
        index = int((handle - 32) / 3)
        tm, d = self._unpack_eeg_channel(data)

        if self.last_tm == 0:
            self.last_tm = tm - 1

        self.data[index] = d
        self.timestamps[index] = timestamp
        # last data received
        if handle == 35:
            if tm != self.last_tm + 1:
                print("missing sample %d : %d" % (tm, self.last_tm))
            self.last_tm = tm

            # calculate index of time samples
            idxs = np.arange(0, 12) + self.sample_index
            self.sample_index += 12

            # affect as timestamps
            timestamps = self.reg_params[1] * idxs + self.reg_params[0]

            # push data
            self.callback(self.data, timestamps)
            self._init_sample()
