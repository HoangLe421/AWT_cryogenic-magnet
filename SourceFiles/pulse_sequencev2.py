import numpy as np

__version__ = '1.0.1'
__docformat__ = 'reStructuredText'

__all__ = ['EPR_pulse', ]

class EPR_pulse(object):
    def __init__(self,sampling_rate=2.4e9,Vpp=500):
        self.sampling_rate = sampling_rate  # Default sampling rate in Hz
        self.Vmax = Vpp/2 # Default voltage peak-to-peak in mV
        self.Vpp = Vpp # Default voltage peak-to-peak in mV

    @staticmethod
    def _parse_phase(phase):
        """
        Convert the phase parameter into radians.

        If a string is provided, it is mapped as follows:
            * 'x' -> 0°
            * 'y' -> 90°
            * '-x' -> 180°
            * '-y' -> 270°

        Otherwise, a numeric value (in degrees) is assumed.

        Parameters
        ----------
        phase : str or float
            Phase specification (either a string or a numeric value in degrees)

        Returns
        -------
        float
            Phase in radians
        """
        if isinstance(phase, str):
            mapping = {'x': 0, 'y': 90, '-x': 180, '-y': 270}
            return np.deg2rad(mapping.get(phase, 0))
        else:
            return np.deg2rad(phase)

    def Gaussian(self, amplitude=1, sigma=10,
                 t_min=-50e-9, t_max=50e-9, phase='x', f_c=500e6):
        """
        Generate a Gaussian pulse.

        Parameters
        ----------
        amplitude : float
            Amplitude of the pulse in mV (default: 1)
        sigma : float
            Standard deviation of the pulse in s (default: 10 ns)
        t_min : float
            Start time of the pulse in s (default: -50 ns)
        t_max : float
            End time of the pulse in s (default: 50 ns)
        phase : str or float
            Phase of the pulse in degrees (default: 'x', i.e. 0)
        f_c : float
            Carrier frequency of the pulse in Hz (default: 500 MHz)

        Returns
        -------
        t : numpy.ndarray
            Time axis in s
        y : numpy.ndarray
            Complex pulse amplitude in mV
        """
        if amplitude > 1:
            raise ValueError("Amplitude must be between 0 and 1.")
        amplitude = self.Vmax * amplitude

        dt = 1 / self.sampling_rate
        t = np.arange(t_min, t_max, dt)

        points = len(t)
        # Ensure the number of points is even for syncing with the digital output channel
        if points%2 != 0:
            t = np.append(t, t[-1] + dt)
        # Calculate the center of the Gaussian
        t0 =  (t_max +t_min) / 2
        envelope = amplitude * np.exp(-((t - t0)**2) / (2 * sigma**2))
        phase_offset = self._parse_phase(phase)
        if f_c != 0:
            y = envelope * np.exp(1j * (2 * np.pi * f_c * t + phase_offset))
        else:
            y = envelope *  np.exp(1j * phase_offset)
        return t, y
    
    def Square(self, amplitude=1, duty_cycle=1,
               t_min=-50e-9, t_max=50e-9, phase='x', f_c=500e6):
        """
        Generate a square pulse.
        Time is in s and amplitude in mV.
        """
        if amplitude > 1:
            raise ValueError("Amplitude must be between 0 and 1.")
        amplitude = self.Vmax * amplitude
        dt = 1 / self.sampling_rate
        t = np.arange(t_min, t_max, dt)
        points = len(t)
        # Ensure the number of points is even for syncing with the digital output channel
        if points%2 != 0:
            t = np.append(t, t[-1] + dt)

        pulse_length = (t_max - t_min)*duty_cycle
        envelope = np.zeros_like(t)
        if duty_cycle > 0:
            envelope[(t >= t_min) & (t <= t_min+pulse_length)] = amplitude

        phase_offset = self._parse_phase(phase)
        if f_c != 0:
            y = envelope * np.exp(1j * (2 * np.pi * f_c * t + phase_offset))
        else:
            y = envelope * np.exp(1j * phase_offset)
        return t, y


    def Chirp(self, amplitude=1, f0=1, f1=5, 
              t_min=-50e-9, t_max=50e-9, points=1000, phase='x'):
        """
        Generate a linear chirp pulse.
        Time is in ns and amplitude in mV.
        """
        t = np.linspace(t_min, t_max, points)
        k = (f1 - f0) / (t_max - t_min)
        base_phase = 2 * np.pi * (f0 * (t - t_min) + 0.5 * k * (t - t_min)**2)
        phase_offset = self._parse_phase(phase)
        total_phase = base_phase + phase_offset
        y = amplitude *  np.exp(1j * phase_offset)
        return t, y
    
    def must_be_64_multiple (self, t_seq, y_seq):
        dt = np.diff(t_seq)[0]
        # Calculate the number of additional points needed
        remainder = len(t_seq) % 64
        if remainder != 0:
            additional_points = 64 - remainder
        else:
            additional_points = 0
        # Extend t_seq with additional points
        t_seq_extended = np.append(t_seq, t_seq[-1] + dt * np.arange(1, additional_points + 1))
        # Extend y_seq with zeros
        y_seq_extended = np.append(y_seq, np.zeros(additional_points, dtype=y_seq.dtype))
        # Update t_seq and y_seq
        t_seq = t_seq_extended
        y_seq = y_seq_extended
        return t_seq, y_seq
    
    def DAC_output(self, y_seq):
        y_dac = (y_seq/self.Vpp +1/2)* (2**16-1)
        return y_dac.astype(np.uint16)
    
    def pulse_sequence(self, steps):
        """
        Build a pulse sequence by concatenating pulses and delays.
        
        Each element in steps is a tuple:
          For pulses: (pulse_type, duration, parameters_dict)
          For a delay: ('delay', duration, optional_parameters_dict)
          
        The time axis for each pulse (or delay) is defined from 0 to duration.
        Pulses are then time-shifted to form one continuous (t, y) sequence.
        
        Returns:
          t_seq : numpy.ndarray
              The overall time axis in ns.
          y_seq : numpy.ndarray
              The overall pulse sequence (complex or real, in mV).
        """
        t_seq = np.array([])
        y_seq = np.array([])
        y_det = np.array([])
        dt = 1 / self.sampling_rate
        current_time = 0
        
        for step in steps:
            pulse_type = step[0].lower()
            duration = step[1]
            if pulse_type == 'delay':
                # For a delay, generate zeros.
                params = step[2] if len(step) > 2 else {}
                t_local = np.arange(0, duration, dt)
                points = len(t_local)
                y_local_ch1 = np.zeros(points, dtype=float)
                y_local_ch2 = np.zeros(points, dtype=float)
            elif pulse_type == 'detection':
                # For a detection step, generate zeros.
                params = step[2] if len(step) > 2 else {}
                params.setdefault('t_min', 0)
                params.setdefault('t_max', duration)
                func = self.Square
                t_local = np.arange(0, duration, dt)
                points = len(t_local)
                y_local_ch1 = np.zeros(points, dtype=float)
                t_local, y_local_ch2 = func(**params)

            else:
                # For a pulse, use the corresponding method.
                params = step[2] if len(step) > 2 else {}
                # Set common defaults: define the pulse over 0 to duration.
                if pulse_type == 'gaussian':
                    params.setdefault('t_min', 0)
                    params.setdefault('t_max', duration)
                    params.setdefault('sigma', duration/6)  # roughly cover duration
                    func = self.Gaussian
                elif pulse_type == 'square':
                    params.setdefault('t_min', 0)
                    params.setdefault('t_max', duration)
                    func = self.Square
                elif pulse_type == 'chirp':
                    params.setdefault('t_min', 0)
                    params.setdefault('t_max', duration)
                    func = self.Chirp
                else:
                    raise ValueError(f"Unknown pulse type: {step[0]}")
                t_local, y_local_ch1 = func(**params)
                y_local_ch2 = np.zeros(len(t_local), dtype=float)
            # Shift local time by the current cumulative time.
            t_local = t_local + current_time
            t_seq = np.concatenate((t_seq, t_local))
            y_seq = np.concatenate((y_seq, y_local_ch1))
            y_det = np.concatenate((y_det, y_local_ch2))
            current_time += duration

        t_seq, y_seq = self.must_be_64_multiple(t_seq, y_seq)
        # Convert the y_seq to DAC output format
        #y_dac = self.DAC_output(y_seq)
        return t_seq, y_seq, y_det
    
    def dig_output(self, steps, tolerance=1e-12):
        """
        This method uses the pulse_sequence method to get (t, y) and then produces a digital
        representation where y=0 for zero values and y=1 where the pulse is active (nonzero).
        """
        t_seq, y_seq, y_det = self.pulse_sequence(steps)
        # Create a digital output: 0 if nearly zero, 1 otherwise.
        dig_y = np.where(np.abs(y_seq) < tolerance, 0, 1)
        return t_seq, dig_y

    def marker (self, steps, tolerance=1e-12):
        """
        This method uses the pulse_sequence method to get (t, y) and then produces a digital
        representation where y=0 for zero values and y=1 where the pulse is active (nonzero).
        """
        t_seq, y_seq, y_det = self.pulse_sequence(steps)
        sampled_y = y_seq[::4]
        # Create a digital output: 0 if nearly zero, 1 otherwise.
        mrk = np.where(np.abs(sampled_y) < tolerance, 0, 1)
        return mrk 

    