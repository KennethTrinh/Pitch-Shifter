import librosa
import numpy as np
import soundfile as sf
import sys
import pyrubberband as pyrb

def Transpose(file, pitch):
    data, sr = librosa.load(file, sr=None, mono=False)
    l = pyrb.pitch_shift(data[0], sr, pitch)#librosa.effects.pitch_shift(data[0], sr, n_steps =pitch, res_type="linear")
    r = pyrb.pitch_shift(data[1], sr, pitch) #librosa.effects.pitch_shift(data[1], sr, n_steps =pitch, res_type="linear")
    y_shifted = np.asfortranarray(np.array([l,r]))
    sf.write(file=file[:-4] + str(pitch) + '.wav', data= np.swapaxes(y_shifted, 0,1), samplerate=sr, format='WAV')



Transpose(sys.argv[1], sys.argv[2])
