# -*- coding: utf-8 -*-
# author: Hoang Le
import numpy as np
import matplotlib.pyplot as plt

class EPR_pulse:
    def __init__(self,sampling_rate=2.5e9):
        self.sampling_rate = sampling_rate  # Default sampling rate in Hz

    @staticmethod
    def _parse_phase(phase):
        """
        Convert the phase parameter into radians.
        If a string is provided, map:
            'x'  -> 0°,'y'  -> 90°,'-x' -> 180°,'-y' -> 270°.
        Otherwise, assume a numeric phase (in degrees).
        """
        if isinstance(phase, str):
            mapping = {'x': 0, 'y': 90, '-x': 180, '-y': 270}
            return np.deg2rad(mapping.get(phase, 0))
        else:
            return np.deg2rad(phase)

    def Gaussian(self, amplitude=100, sigma=10, 
                 t_min=-50e-9, t_max=50e-9, phase='x', f_c=500e6):
        """
        Generate a Gaussian pulse.
        Time is in s and amplitude in mV. f_c is the carrier frequency in Hz.
        """
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
    
    def Square(self, amplitude=100, duty_cycle=1,
               t_min=-50e-9, t_max=50e-9, phase='x', f_c=500e6):
        """
        Generate a square pulse.
        Time is in s and amplitude in mV.
        """
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


    def Chirp(self, amplitude=100, f0=1, f1=5, 
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
                y_local = np.zeros(points, dtype=float)
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
                t_local, y_local = func(**params)
            # Shift local time by the current cumulative time.
            t_local = t_local + current_time
            t_seq = np.concatenate((t_seq, t_local))
            y_seq = np.concatenate((y_seq, y_local))
            current_time += duration

        t_seq, y_seq = self.must_be_64_multiple(t_seq, y_seq)

        return t_seq, y_seq

# ------------------------------
# Example usage:
# Build a sequence:
#   1. A Gaussian pulse 90 ns long, amplitude=100 mV, phase 'x'.
#   2. A delay of 1000 ns.
#   3. A square pulse 45 ns long, amplitude=100 mV, phase '-y'.
#   4. A delay of 1000 ns.
#   5. A Gaussian pulse 90 ns long, amplitude=100 mV, phase 30 degree.
# The structure for steps (list of tuples) is:
#  steps = [ (pulse type1, duration, {library of other parameters})
#            (delay, duration, {'points':##}),
#            (pulse type2, duration, {library of other parameters}),
#            (pulse type3, duration, {library of other parameters}),] 
# 
# ------------------------------

if __name__ == '__main__':
    p = EPR_pulse()  # Set a sampling rate of 2.4 GHz
    
    steps = [
        ('Gaussian', 100e-9, {'amplitude': 100 ,'phase': 'y' }),
        ('delay', 400e-9),
        ('Square', 40e-9, {'amplitude': 1000, 'phase': 90}),
        ('delay', 400e-9),
        ('Gaussian', 90e-9, {'amplitude': 100, 'phase': 150})
    ]
    
    t_seq, y_seq = p.pulse_sequence(steps)
    
    print (len(t_seq))
    # Plot the overall sequence: real and imaginary components.
    plt.figure(figsize=(12, 6))
    plt.plot(t_seq, np.real(y_seq), label='Real part')
    plt.plot(t_seq, np.imag(y_seq), label='Imaginary part', linestyle='--')
    plt.xlabel('Time (s)')
    plt.ylabel('Amplitude (mV)')
    plt.title('Pulse Sequence: Gaussian, Delay, Square, Delay, Gaussian')
    plt.legend()
    plt.show()