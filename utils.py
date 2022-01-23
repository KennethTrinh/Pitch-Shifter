import numpy as np
from scipy.signal import get_window
from math import fmod, pi, floor, cos, sin
from scipy.signal import find_peaks
import heapq

def build_dft_rescale_lookup(n_bins, shift_factor):
    """
    Build lookup table from DFT bins to rescaled bins.
    n_bins: Number of bins in positive half of DFT.
    shift_factor: Shift factor for voice effect.
    shift_idx: Mapping from bin to rescaled bin.
    return max_bin: Maximum bin until rescaled is less than `n_bins`.
    """
    shift_idx = np.zeros(n_bins, dtype=np.int16)
    max_bin = n_bins
    for k in range(n_bins):
        ix = floor(k * shift_factor + 0.5)
        if ix<n_bins:
            shift_idx[k] = ix
        else:
            max_bin = ix
            break
    return shift_idx, max_bin

def dft_rescale(x, n_bins, shift_idx, max_bin, phase_vocoder):
    """
    Rescale spectrum using the lookup table.
    x: Input segment in time domain
    n_bins: Number of bins in positive half of DFT.
    shift_idx: Mapping from bin to rescaled bin.
    max_bin: Maximum bin until rescaled is less than `n_bins`.
    return: Pitch-shifted audio segment in time domain.
    """
    X = np.fft.rfft(x)
    Y = np.zeros(n_bins, dtype=np.complex)
    max_bin = min(max_bin, len(X))
    Y[shift_idx[range(max_bin)]] += X[range(max_bin)]
    #Y[shift_idx[0]] = X[0]
    #parity = (len(X) % 2 == 0)
    #Y = np.r_[Y, np.conj(Y[-2:0:-1])] if parity else np.r_[Y, np.conj(Y[-1:0:-1])] <-- too slow
    Y = phase_vocoder.calc_phase(Y)
    return np.fft.irfft(Y), phase_vocoder

# class PhaseVocoder:
#     """Vectorized implementation of phase vocoder with peak detection --> no idea what I'm doing """
#     def __init__(self, window_size, pitch_ratio):
#         self.window_size = window_size
#         self.synthesis_hopsize = window_size//4
#         self.analysis_hopsize = int(self.synthesis_hopsize//pitch_ratio)
#         self.last_phase = np.zeros(window_size//2+1)
#         self.accum_phase = np.zeros(window_size//2+1)
#         self.expected_phase = np.linspace(0, window_size//2, window_size//2+1)*2*np.pi*self.analysis_hopsize//window_size  # expected phase
#         self.pk_indices = range(window_size//2)
#     def calc_phase(self, current_frame):
#         """Saves previous phase values for calculation of next frame"""
#         current_phase = np.angle(current_frame)
#         current_magn = abs(current_frame)
#         delta_phase = np.unwrap(current_phase - self.last_phase - self.expected_phase)
#         self.last_phase = current_phase.copy()
#         self.accum_phase[self.pk_indices] = self.accum_phase[self.pk_indices] + (delta_phase[self.pk_indices] + self.expected_phase[self.pk_indices])*self.synthesis_hopsize/self.analysis_hopsize
#         rotation_angle = self.accum_phase[self.pk_indices] - current_phase[self.pk_indices]
#         peak = np.array(self.pk_indices[0:-1])
#         next_peak = np.array(self.pk_indices[1:])
#         end_point = (peak + next_peak)//2
#         start_point = np.r_[0, end_point[:-1]]
#         M = [start_point, peak, end_point] #Pre-computed matrix
#         for k in range(len(self.pk_indices)-1):
#             ri_indices = [i for i in range(M[0][k], M[2][k]) if i!=M[1][k]]#np.r_[np.arange(M[0][k],M[1][k]) , np.arange(M[2][k],M[3][k])]
#             self.accum_phase[ri_indices] = rotation_angle[k] + current_phase[ri_indices]
#         ri_indices = range(end_point[-1], self.pk_indices[-1]) if len(end_point)>0 else []
#         self.accum_phase[ri_indices] = rotation_angle[len(self.pk_indices)-1] + current_phase[ri_indices]
#         self.pk_indices, _ = find_peaks(current_magn)
#         if len(self.pk_indices) == 0: self.pk_indices = [1]
#         return current_magn*np.exp(1j*self.accum_phase)
#     def update(self, pitch_ratio):
#         """ Called when pitch is changed """
#         self.analysis_hopsize = int(self.synthesis_hopsize//pitch_ratio)
#         self.expected_phase = np.linspace(0, self.window_size//2, self.window_size//2+1)*2*np.pi*self.analysis_hopsize//self.window_size


class PhaseVocoder:
    """Vectorized implementation of phase vocoder with peak detection --> no idea what I'm doing """
    def __init__(self, window_size, pitch_ratio):
        self.window_size = window_size
        self.synthesis_hopsize = window_size//4
        self.analysis_hopsize = int(self.synthesis_hopsize//pitch_ratio)
        self.alpha = self.synthesis_hopsize/self.analysis_hopsize
        self.HALF_FFT = window_size//2+1
        self.last_phase = np.zeros(self.HALF_FFT) #frame n − 1
        self.accum_phase = np.zeros(self.HALF_FFT)
        self.last_accum_phase = np.zeros(self.HALF_FFT)
        self.expected_phase = np.linspace(0, window_size//2, self.HALF_FFT)*2*np.pi*self.analysis_hopsize//window_size  # expected phase (2049,)
        self.last_magnitudes = np.zeros(self.HALF_FFT) #frame n − 1
    def calc_phase(self, current_frame):
        """Saves previous phase values for calculation of next frame"""
        current_phase = np.angle(current_frame)
        current_magn = abs(current_frame)
        delta_phase = np.unwrap(current_phase - self.last_phase - self.expected_phase)
        phase_derivative = self.expected_phase + delta_phase
        frequency_derivative = np.unwrap( np.r_[0, (current_phase[1:] - current_phase[:-1])] )
        #self.accum_phase += phase_derivative*(self.synthesis_hopsize/self.analysis_hopsize) #phi(k, n+1)
        self.Gradient_Heap(current_magn, phase_derivative, frequency_derivative)
        self.last_accum_phase = self.accum_phase.copy()
        self.last_phase = current_phase
        self.last_magnitudes = current_magn
        return current_magn*np.exp(1j*self.accum_phase)
    def update(self, pitch_ratio):
        """ Called when pitch is changed """
        self.analysis_hopsize = int(self.synthesis_hopsize//pitch_ratio)
        self.expected_phase = np.linspace(0, self.window_size//2, self.HALF_FFT)*2*np.pi*self.analysis_hopsize//self.window_size
        self.alpha = self.synthesis_hopsize/self.analysis_hopsize
    def Gradient_Heap(self, current_magn, phase_derivative, frequency_derivative, threshold=0.5):
        """Implementation gradient propagation algorithm - Makes all magnitudes negative for Max heap """
        #threshold = threshold* max( current_magn.max(), self.last_magnitudes.max() )
        heap = []
        I = set()
        for i in range(self.HALF_FFT):
            if self.last_magnitudes[i] > threshold:
                heapq.heappush(heap, (-self.last_magnitudes[i], i, 0) )
            if current_magn[i] > threshold:
                I.add( (i, 1) )
        # previous_indices = np.where( self.last_magnitudes > threshold )[0]
        # heap = list( zip(self.last_magnitudes[previous_indices] * -1, previous_indices, np.zeros(previous_indices.shape[0]) ) )
        # heapq.heapify(heap) # initialize with all elements from frame n - 1
        # current_indices = np.where( current_magn > threshold )[0]
        # I = set( zip( current_indices, np.ones(current_indices.shape[0]) ) ) #visited
        while I and heap:
            G, k, n = heapq.heappop(heap)
            if n == 0:
                if (k, n+1) in I:
                    self.accum_phase[k] = self.last_accum_phase[k] + phase_derivative[k] * self.alpha
                    I.remove( (k, n+1) )
                    heapq.heappush( heap, (-current_magn[k], k , n+1) )
            if n == 1:
                if (k+1, n) in I:
                    self.accum_phase[k + 1] = self.accum_phase[k] +  frequency_derivative[k + 1] * self.alpha
                    I.remove( (k+1, n) )
                    heapq.heappush( heap, (-current_magn[k+1], k+1 , n) )
                if (k-1, n) in I:
                    self.accum_phase[k - 1] = self.accum_phase[k] +  frequency_derivative[k - 1] * self.alpha
                    I.remove( (k-1, n) )
                    heapq.heappush( heap, (-current_magn[k-1], k-1 , n) )
