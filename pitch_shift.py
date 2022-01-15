import pyaudio
import numpy as np
from utils import dft_rescale, build_dft_rescale_lookup, PhaseVocoder
import librosa



input_wav = './Red.mp3'
shift_factor = 2**(0/12) #start at regular pitch

signal, samp_freq = librosa.load(input_wav, sr=None, mono=True)
data_type = signal.dtype

# derived parameters
GRAIN_LEN_SAMP = 4096
STRIDE = 1024
OVERLAP_LEN = GRAIN_LEN_SAMP-STRIDE
LARGER_STRIDE = STRIDE > OVERLAP_LEN
even = (GRAIN_LEN_SAMP % 2 == 0)
N_BINS = GRAIN_LEN_SAMP// 2 + 1 if even else (GRAIN_LEN_SAMP + 1) // 2

# allocate input and output buffers
input_buffer = np.zeros(STRIDE, dtype=data_type)
output_buffer = np.zeros(STRIDE, dtype=data_type)

# state variables and constants
def init():
    # lookup table for tapering window
    global WIN, STRIDE, OVERLAP_LEN, LARGER_STRIDE, input_buffer, output_buffer
    WIN = np.hanning(GRAIN_LEN_SAMP) #scipy implementation is not symmetric!
    # lookup table for DFT rescaling
    global SHIFT_IDX, MAX_BIN
    SHIFT_IDX, MAX_BIN = build_dft_rescale_lookup(N_BINS, shift_factor)
    # (state variables)
    global x_prev
    x_prev = np.zeros(GRAIN_LEN_SAMP).astype(np.float32)
    # intermediate values
    global input_concat, grain, prev_grain
    input_concat = np.zeros(GRAIN_LEN_SAMP).astype(np.float32)
    grain = np.zeros(GRAIN_LEN_SAMP).astype(np.float32)
    prev_grain = np.zeros(GRAIN_LEN_SAMP).astype(np.float32)
    global phase_vocoder
    phase_vocoder = PhaseVocoder(GRAIN_LEN_SAMP, shift_factor)
    if not LARGER_STRIDE:
        x_prev, prev_grain = np.zeros(OVERLAP_LEN).astype(np.float32), np.zeros(OVERLAP_LEN).astype(np.float32)#deque(maxlen=OVERLAP_LEN), deque(maxlen=OVERLAP_LEN)


#import time
def process(input_buffer, output_buffer, buffer_len):
    #starttime = time.time()
    global x_prev, prev_grain, grain, phase_vocoder
    # append samples from previous buffer
    input_concat[:OVERLAP_LEN], input_concat[OVERLAP_LEN:] = x_prev[:OVERLAP_LEN], input_buffer
    # Apply effect: apply window then rescale
    grain, phase_vocoder = dft_rescale(input_concat*WIN, N_BINS, SHIFT_IDX, MAX_BIN, phase_vocoder)
    grain=grain*WIN
    #No loops due to latency constraints
    output_buffer[:STRIDE] = prev_grain[:STRIDE] + grain[:STRIDE]
    x_prev[:2*STRIDE], x_prev[2*STRIDE:] =  x_prev[STRIDE:], input_buffer
    prev_grain[:2*STRIDE], prev_grain[2*STRIDE:] = prev_grain[STRIDE:], grain[-STRIDE:]
    prev_grain[:OVERLAP_LEN-STRIDE] = prev_grain[:OVERLAP_LEN-STRIDE] +  grain[STRIDE:OVERLAP_LEN]
    #print('That took {} seconds'.format(time.time() - starttime))

init()
count=0
pitchChanged = False

def callback(in_data, frame_count, time_info, status):
    global count, shift_factor, SHIFT_IDX, MAX_BIN, pitchChanged, phase_vocoder
    if pitchChanged:
        phase_vocoder.update(shift_factor)
        pitchChanged=False
        SHIFT_IDX, MAX_BIN = build_dft_rescale_lookup(N_BINS, shift_factor)
    start_idx, end_idx = frame_count*count, frame_count*(count+1)
    input_buffer = signal[start_idx:end_idx]
    process(input_buffer, output_buffer, STRIDE)
    ret_data = output_buffer.tobytes()
    count+=1
    return (ret_data, pyaudio.paContinue)


p = pyaudio.PyAudio()
stream = p.open(format = pyaudio.paFloat32,
                channels=1,
                rate=samp_freq,
                output=True,
                frames_per_buffer=STRIDE,
                start=True,
                stream_callback=callback)

#I'll prolly turn this into a GUI but here's controls for now
import readchar
from math import log2
while(True):
    key = readchar.readkey()
    if key == 'p':
        stream.stop_stream() if stream.is_active() else stream.start_stream()
    elif key == '\x1b[C':       #Right arrow key
        shift_factor *= (2**(1/12))
        pitchChanged=True
        print(int(log2(shift_factor)*12))
    elif key == '\x1b[D':       #Left arrow key
        shift_factor *= (2**(-1/12))
        pitchChanged=True
        print(int(log2(shift_factor)*12))
    elif key == 's':
        stream.stop_stream()
        break
    elif key == '\x1b[A':       #Up arrow key
        count+=45
    elif key == '\x1b[B':       #Down arrow key
        count-=45
