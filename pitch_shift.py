import pyaudio
import numpy as np
from utils import dft_rescale, build_dft_rescale_lookup, PhaseVocoder
import librosa
import time


class PitchShifter:
    def __init__(self, input_wav, shift_factor):
        "Must re-initialize whenever loading a new song"
        self.shift_factor = shift_factor
        self.signal, self.samp_freq = librosa.load(input_wav, sr=None, mono=True)
        #derived parameters
        self.GRAIN_LEN_SAMP = 4096
        self.STRIDE = 1024
        self.OVERLAP_LEN = self.GRAIN_LEN_SAMP-self.STRIDE
        self.N_BINS = self.GRAIN_LEN_SAMP// 2 + 1
        self.DURATION = round( len(self.signal) / self.samp_freq , 3)
        self.input_buffer = np.zeros(self.STRIDE, dtype=np.float32)
        self.output_buffer= np.zeros(self.STRIDE, dtype=np.float32)
        self.WIN = np.hanning(self.GRAIN_LEN_SAMP)
        self.SHIFT_IDX, self.MAX_BIN = build_dft_rescale_lookup(self.N_BINS, shift_factor)
        self.x_prev = np.zeros(self.OVERLAP_LEN).astype(np.float32)
        self.prev_grain = np.zeros(self.OVERLAP_LEN).astype(np.float32)
        self.input_concat = np.zeros(self.GRAIN_LEN_SAMP).astype(np.float32)
        self.grain = np.zeros(self.GRAIN_LEN_SAMP).astype(np.float32)
        self.phase_vocoder = PhaseVocoder(self.GRAIN_LEN_SAMP, shift_factor)
        self.count=0
        self.pitchChanged = False
        self.Finish = False
        self.p = pyaudio.PyAudio()
        self.stream=self.p.open(format = pyaudio.paFloat32,
                        channels=1,
                        rate=self.samp_freq,
                        output=True,
                        frames_per_buffer=self.STRIDE,
                        start=False,
                        stream_callback=self.callback)

    def process(self, input_buffer, output_buffer, buffer_len):
        """Called every stride/hop in the callback function """
        self.input_concat[:self.OVERLAP_LEN], self.input_concat[self.OVERLAP_LEN:] = self.x_prev[:self.OVERLAP_LEN], input_buffer
        self.grain, self.phase_vocoder = dft_rescale(self.input_concat*self.WIN, self.N_BINS, self.SHIFT_IDX, self.MAX_BIN, self.phase_vocoder)
        self.grain*=self.WIN
        #Overlap-add without loops due to latency constraints
        update = self.OVERLAP_LEN - self.STRIDE
        self.output_buffer[:self.STRIDE] = self.prev_grain[:self.STRIDE] + self.grain[:self.STRIDE]
        self.x_prev[:update], self.x_prev[update:] =  self.x_prev[self.STRIDE:], input_buffer
        self.prev_grain[:update], self.prev_grain[update:] = self.prev_grain[self.STRIDE:], self.grain[-self.STRIDE:]
        self.prev_grain[:update] +=  self.grain[self.STRIDE:self.OVERLAP_LEN]

    def callback(self, in_data, frame_count, time_info, status):
        """Moves the audio forward using the count pointer --> Called when self.stream.is_active()"""
        if self.pitchChanged:
            self.phase_vocoder.update(self.shift_factor)
            self.pitchChanged=False
            self.SHIFT_IDX, self.MAX_BIN = build_dft_rescale_lookup(self.N_BINS, self.shift_factor)
        start_idx, end_idx = frame_count*self.count, frame_count*(self.count+1)
        input_buffer = self.signal[start_idx:end_idx]
        if len(input_buffer) < frame_count:
            self.Finish = True
            return (in_data, pyaudio.paComplete)
        self.process(input_buffer, self.output_buffer, self.STRIDE)
        ret_data = self.output_buffer.tobytes()
        self.count+=1
        return (ret_data, pyaudio.paContinue)

    def play(self):
        """Starts the stream"""
        self.stream.start_stream()

    def pause(self):
        """Pauses the stream"""
        self.stream.stop_stream()

    def getPitch(self):
        """Returns pitch scale ratio --> One semitone up is a multiplication by 2^(1/12) """
        return self.shift_factor

    def setPitch(self, shift_factor):
        """Sets pitch scale ratio --> One semitone up is a multiplication by 2^(1/12) """

        assert shift_factor > -3 and shift_factor <3, "Pitch must be bounded between 2 octaves"
        self.pitchChanged = True
        self.shift_factor = shift_factor

    def getTime(self):
        """Returns position of song in seconds """
        return self.count * self.STRIDE / self.samp_freq

    def setTime(self, seconds):
        """Sets song with seconds as input parameter """
        assert seconds >= 0 and seconds < self.DURATION, "Choose a valid duration within the boundaries of song"
        self.count = int( seconds * self.samp_freq / self.STRIDE )

    def getData(self):
        """Returns raw wave data """
        return self.output_buffer

    def getAmpSpectrum(self):
        """Returns amplitudes of real FFT """
        return np.abs( np.fft.rfft(self.output_buffer) )

if __name__ == '__main__': #testing
    input_wav = './Red.mp3'
    audio = PitchShifter(input_wav, 2**(0/12))
    audio.play()
    import readchar
    from math import log2
    while(True):
        key = readchar.readkey()
        if key == 'p':
            audio.stream.stop_stream() if audio.stream.is_active() else audio.stream.start_stream()
        elif key == '\x1b[C':       #Right arrow key -- increment current pitch by one semi-tone
            audio.setPitch( audio.getPitch() * (2**(1/12) ))
            print(int(log2(audio.getPitch())*12))
        elif key == '\x1b[D':       #Left arrow key -- decrement current pitch by one semi-tone
            audio.setPitch( audio.getPitch() * (2**(-1/12) ))
            print(int(log2(audio.getPitch())*12))
        elif key == 's':
            audio.stream.stop_stream()
            break
        elif key == '\x1b[A':       #Up arrow key
            audio.count+=45
        elif key == '\x1b[B':       #Down arrow key
            audio.count-=45
        elif key == 't':
            print(audio.getTime(), 'seconds')
        elif key == '3':
            audio.setTime(239)
            print(audio.getTime(), 'set to 239 seconds')
        elif key == 'f':
            print(audio.didFinish())
        elif key == 'l':
            audio.pause()
            audio = PitchShifter('Kanye.mp3', 2**(0/12))
            audio.play()

"""
input_wav = './Red.mp3'
shift_factor = 2**(0/12) #start at regular pitch

signal, samp_freq = librosa.load(input_wav, sr=None, mono=True)


# derived parameters
GRAIN_LEN_SAMP = 4096
STRIDE = 1024
OVERLAP_LEN = GRAIN_LEN_SAMP-STRIDE
LARGER_STRIDE = STRIDE > OVERLAP_LEN
even = (GRAIN_LEN_SAMP % 2 == 0)
N_BINS = GRAIN_LEN_SAMP// 2 + 1 if even else (GRAIN_LEN_SAMP + 1) // 2
DURATION = round( len(signal) / samp_freq , 3)

# allocate input and output buffers
input_buffer = np.zeros(STRIDE, dtype=np.float32)
output_buffer = np.zeros(STRIDE, dtype=np.float32)

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

"""
