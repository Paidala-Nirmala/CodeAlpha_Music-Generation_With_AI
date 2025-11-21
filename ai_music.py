"""
AI Music Studio — Full Project (single-file)
Author: Chitti (Assistant for Nirmala)

This version fixes:
- Non-blocking playback (uses winsound on Windows, falls back to playsound in a thread)
- Non-blocking matplotlib visualization (plt.show(block=False))
- Unique WAV filenames and safe BASE_DIR saving (avoids PermissionError)
- No changes to UI colors, instruments, or audio logic
"""

import os
import time
import math
import struct
import wave
import threading
import random
import shutil
import platform
from tkinter import *
from tkinter import ttk, filedialog, messagebox

# Base directory (safe output folder)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Try import numpy (required for audio generation)
try:
    import numpy as np
except Exception as e:
    raise ImportError("numpy is required. Install with: pip install numpy")

# Playback: prefer winsound on Windows (non-blocking), else playsound in thread
playsound = None
try:
    from playsound import playsound as _playsound
    playsound = _playsound
except Exception:
    playsound = None

# winsound available on Windows
winsound = None
if platform.system() == "Windows":
    try:
        import winsound
    except Exception:
        winsound = None

# pydub for WAV -> MP3 conversion
try:
    from pydub import AudioSegment
    pydub_available = True
except Exception:
    pydub_available = False

# matplotlib for visualization
try:
    import matplotlib.pyplot as plt
    mpl_available = True
except Exception:
    mpl_available = False

# ======================================
# Audio utilities
# ======================================
SAMPLE_RATE = 44100

def generate_tone(frequency, duration, volume=0.5, waveform="sine", sample_rate=SAMPLE_RATE, instrument=None):
    num_samples = int(sample_rate * duration)
    audio = np.zeros(num_samples, dtype=np.float32)

    for i in range(num_samples):
        t = i / sample_rate
        if instrument:
            # instrument will override waveform if provided
            value = instrument_wave(instrument, frequency, t)
        else:
            if waveform == "sine":
                value = math.sin(2 * math.pi * frequency * t)
            elif waveform == "square":
                value = 1.0 if math.sin(2 * math.pi * frequency * t) >= 0 else -1.0
            elif waveform == "saw":
                value = 2 * (t * frequency - math.floor(0.5 + t * frequency))
            elif waveform == "triangle":
                value = 2 * abs(2 * (t * frequency - math.floor(0.5 + t * frequency))) - 1
            elif waveform == "noise":
                value = random.uniform(-1.0, 1.0)
            else:
                value = 0.0

        audio[i] = value * volume

    return audio

# ======================================
# Instrument synthesis via harmonics
# ======================================

def piano_wave(freq, t):
    # basic harmonic stack for a soft piano-like tone
    return (
        1.0 * math.sin(2 * math.pi * freq * t)
        + 0.5 * math.sin(2 * math.pi * freq * 2 * t)
        + 0.25 * math.sin(2 * math.pi * freq * 3 * t)
    ) * math.exp(-3 * t)


def flute_wave(freq, t):
    # pure sine-like
    return math.sin(2 * math.pi * freq * t) * math.exp(-0.8 * t)


def pad_wave(freq, t):
    return (
        0.6 * math.sin(2 * math.pi * freq * t)
        + 0.3 * math.sin(2 * math.pi * 0.5 * freq * t)
        + 0.2 * math.sin(2 * math.pi * 1.5 * freq * t)
    )


def bass_wave(freq, t):
    return math.sin(2 * math.pi * (freq * 0.5) * t) * math.exp(-1.5 * t)


def instrument_wave(name, freq, t):
    name = name.lower()
    if name == "piano":
        return piano_wave(freq, t)
    if name == "flute":
        return flute_wave(freq, t)
    if name == "pad":
        return pad_wave(freq, t)
    if name == "bass":
        return bass_wave(freq, t)
    # fallback
    return math.sin(2 * math.pi * freq * t)

# ======================================
# Save WAV (returns full path)
# ======================================

def save_wav(filename, audio_data, sample_rate=SAMPLE_RATE):
    """
    Save numpy audio_data (float in [-1,1] or int16) to a WAV file and return full path.
    filename can be a base name like 'happy_music.wav' — this function will write into BASE_DIR
    and make the filename unique to avoid collision/locks.
    """
    # Ensure numpy array
    audio = np.asarray(audio_data)

    # Convert floats in [-1,1] to int16
    if np.issubdtype(audio.dtype, np.floating):
        audio = np.clip(audio, -1.0, 1.0)
        audio_int16 = (audio * 32767).astype(np.int16)
    elif np.issubdtype(audio.dtype, np.integer):
        audio_int16 = audio.astype(np.int16)
    else:
        raise ValueError("Unsupported audio_data dtype for save_wav")

    # make unique filename to avoid collisions (timestamp ms)
    base, ext = os.path.splitext(filename)
    if ext == '':
        ext = '.wav'
    unique_name = f"{base}_{int(time.time()*1000)}{ext}"
    file_path = os.path.join(BASE_DIR, unique_name)

    # Write WAV using wave module
    with wave.open(file_path, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # bytes (int16)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    return file_path

# ======================================
# WAV -> MP3 using pydub
# ======================================

def wav_to_mp3(wav_path, mp3_path, bitrate='192k'):
    if not pydub_available:
        raise RuntimeError('pydub is required for MP3 export. Install with: pip install pydub')
    if not shutil.which('ffmpeg'):
        raise RuntimeError('ffmpeg not found in PATH. Install ffmpeg to enable MP3 export')
    audio = AudioSegment.from_wav(wav_path)
    audio.export(mp3_path, format='mp3', bitrate=bitrate)

# ======================================
# Playback (non-blocking)
# ======================================

def _playsound_thread(path):
    try:
        playsound(path)
    except Exception as e:
        print("playsound failed:", e)

def play_wav_nonblocking(filepath):
    """
    Plays WAV filepath without blocking the main GUI thread.
    Prefer winsound on Windows (SND_ASYNC) for true non-blocking playback.
    Otherwise start playsound in a background thread.
    """
    # Ensure full path is a string
    path = str(filepath)

    if winsound:
        try:
            # SND_FILENAME plays a file; SND_ASYNC returns immediately
            winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception as e:
            # fallback to playsound thread
            print("winsound playback failed, falling back to playsound:", e)

    if playsound:
        t = threading.Thread(target=_playsound_thread, args=(path,), daemon=True)
        t.start()
        return

    # If no playback lib available, inform user
    print('No playback library available. Install playsound (pip install playsound==1.2.2) or use Windows.')

# ======================================
# AI Melody (Markov chain) & notes
# ======================================

NOTE_FREQ = {
    'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23,
    'G4': 392.00, 'A4': 440.00, 'B4': 493.88, 'C5': 523.25,
    'A3': 220.00, 'Bb4': 466.16, 'Db4': 277.18, 'Gb4': 369.99
}

training_melody = [
    'C4','D4','E4','G4','A4',
    'A4','G4','E4','D4','C4',
    'C4','E4','G4','C5',
    'G4','E4','D4','C4'
]


def build_markov_chain(melody):
    markov = {}
    for i in range(len(melody)-1):
        curr = melody[i]
        nxt = melody[i+1]
        markov.setdefault(curr, []).append(nxt)
    return markov

MARKOV = build_markov_chain(training_melody)


def generate_ai_melody(length=16):
    melody = []
    current = random.choice(training_melody)
    for _ in range(length):
        melody.append(current)
        if current in MARKOV:
            current = random.choice(MARKOV[current])
        else:
            current = random.choice(training_melody)
    return melody


def melody_to_frequencies(melody):
    return [NOTE_FREQ.get(note, 440.0) for note in melody]

# ======================================
# Emotion-based melodies
# ======================================

emotion_patterns = {
    'happy': ['C4','E4','G4','C5','A4','G4','E4'],
    'sad': ['A3','C4','D4','F4','E4','D4','C4'],
    'romantic': ['C4','E4','G4','B4','A4','G4','E4','D4'],
    'suspense': ['C4','Db4','E4','Gb4','A4','Bb4','C5']
}


def generate_emotional_melody(emotion, length=16):
    base = emotion_patterns.get(emotion, emotion_patterns['happy'])
    return [random.choice(base) for _ in range(length)]

# ======================================
# Beat / Drum generator
# ======================================

def kick_drum_sample(duration=0.5, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    # decaying sine for kick
    return (np.sin(2 * math.pi * 60 * t) * np.exp(-8 * t)).astype(np.float32)


def snare_drum_sample(duration=0.25, sample_rate=SAMPLE_RATE):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    noise = np.random.uniform(-1, 1, t.shape)
    return (noise * np.exp(-20 * t)).astype(np.float32)


def generate_beat(pattern=['kick','snare','kick','snare'], tempo=100):
    beat_audio = np.array([], dtype=np.float32)
    beat_unit = 60.0 / tempo
    for part in pattern:
        if part == 'kick':
            s = kick_drum_sample(beat_unit)
        elif part == 'snare':
            s = snare_drum_sample(beat_unit)
        else:
            s = np.zeros(int(SAMPLE_RATE * beat_unit), dtype=np.float32)
        beat_audio = np.concatenate([beat_audio, s])
    return beat_audio

# ======================================
# Visualizer (non-blocking)
# ======================================

def visualize_waveform(audio, sample_rate=SAMPLE_RATE, samples=2000):
    if not mpl_available:
        messagebox.showerror('matplotlib missing', 'matplotlib is required for visualization. Install with pip install matplotlib')
        return
    plt.figure(figsize=(8,3))
    plt.plot(audio[:samples])
    plt.title('Waveform (first {} samples)'.format(samples))
    plt.xlabel('Sample')
    plt.ylabel('Amplitude')
    plt.tight_layout()
    # non-blocking show so GUI remains usable
    try:
        plt.show(block=False)
        # small pause to ensure window appears
        plt.pause(0.001)
    except Exception:
        # fallback to blocking if backend doesn't support non-blocking
        plt.show()

# ======================================
# Tkinter UI
# ======================================

root = Tk()
root.title('AI Music Studio — Chitti')
root.geometry('700x760')
root.configure(bg='#2e003e')

# Top label
Label(root, text='🎶 AI Music Studio — Chitti', font=('Arial', 20, 'bold'), bg='#2e003e', fg='white').pack(pady=8)

# Frame for manual generation
frame_manual = Frame(root, bg='#2e003e')
frame_manual.pack(pady=6)

Label(frame_manual, text='Frequency (Hz):', bg='#2e003e', fg='white').grid(row=0, column=0, sticky='w')
freq_entry = Entry(frame_manual, width=10, bg='#4b0082', fg='white')
freq_entry.grid(row=0, column=1, padx=6)
freq_entry.insert(0,'440')

Label(frame_manual, text='Duration (sec):', bg='#2e003e', fg='white').grid(row=0, column=2, sticky='w')
duration_entry = Entry(frame_manual, width=10, bg='#4b0082', fg='white')
duration_entry.grid(row=0, column=3, padx=6)
duration_entry.insert(0,'2')

Label(frame_manual, text='Volume (0.0-1.0):', bg='#2e003e', fg='white').grid(row=1, column=0, sticky='w')
volume_entry = Entry(frame_manual, width=10, bg='#4b0082', fg='white')
volume_entry.grid(row=1, column=1, padx=6)
volume_entry.insert(0,'0.5')

Label(frame_manual, text='Waveform / Instrument:', bg='#2e003e', fg='white').grid(row=1, column=2, sticky='w')
waveform_values = ['sine','square','saw','triangle','noise','piano','flute','pad','bass']
waveform_box = ttk.Combobox(frame_manual, values=waveform_values, width=12)
waveform_box.set('sine')
waveform_box.grid(row=1, column=3, padx=6)

# MP3 save controls
save_mp3_var = IntVar(value=0)
Checkbutton(root, text='Save as MP3', variable=save_mp3_var, bg='#2e003e', fg='white', selectcolor='#2e003e').pack(pady=6)
Label(root, text='MP3 filename (optional):', bg='#2e003e', fg='white').pack()
mp3_name_entry = Entry(root, width=40, bg='#4b0082', fg='white')
mp3_name_entry.pack(pady=4)

Label(root, text='MP3 Bitrate:', bg='#2e003e', fg='white').pack()
bitrate_box = ttk.Combobox(root, values=['128k','192k','256k','320k'], width=10)
bitrate_box.set('192k')
bitrate_box.pack(pady=4)

# Generate & Play functions

def _generate_and_play_manual():
    try:
        freq = float(freq_entry.get())
        duration = float(duration_entry.get())
        volume = float(volume_entry.get())
    except Exception:
        messagebox.showerror('Invalid input', 'Enter numeric values for frequency, duration, volume')
        return
    waveform = waveform_box.get()
    instrument = None
    if waveform in ['piano','flute','pad','bass']:
        instrument = waveform
        waveform = 'sine'

    audio = generate_tone(freq, duration, volume, waveform, SAMPLE_RATE, instrument=instrument)
    wav_file = 'manual_generated.wav'
    wav_path = save_wav(wav_file, audio)
    play_wav_nonblocking(wav_path)

    if save_mp3_var.get():
        mp3_name = mp3_name_entry.get().strip()
        if mp3_name == '':
            mp3_name = filedialog.asksaveasfilename(defaultextension='.mp3', filetypes=[('MP3','*.mp3')])
            if not mp3_name:
                return
        elif not mp3_name.lower().endswith('.mp3'):
            mp3_name += '.mp3'
        try:
            wav_to_mp3(wav_path, mp3_name, bitrate=bitrate_box.get())
            messagebox.showinfo('Saved', f'MP3 saved to {mp3_name}')
        except Exception as e:
            messagebox.showerror('MP3 Save Failed', str(e))

Button(root, text='Generate & Play Manual Sound', command=_generate_and_play_manual, bg='#ff4dd2', fg='white', font=('Arial', 12)).pack(pady=8)

# AI Composer frame
frame_ai = Frame(root, bg='#2e003e')
frame_ai.pack(pady=6)

Label(frame_ai, text='AI Composer (Markov)', bg='#2e003e', fg='white').grid(row=0, column=0, columnspan=4)

Label(frame_ai, text='Length (notes):', bg='#2e003e', fg='white').grid(row=1, column=0)
ai_length = Entry(frame_ai, width=6, bg='#4b0082', fg='white')
ai_length.grid(row=1, column=1)
ai_length.insert(0,'16')

Label(frame_ai, text='Note Duration (sec):', bg='#2e003e', fg='white').grid(row=1, column=2)
ai_note_dur = Entry(frame_ai, width=6, bg='#4b0082', fg='white')
ai_note_dur.grid(row=1, column=3)
ai_note_dur.insert(0,'0.3')


def _ai_generate_and_play():
    try:
        length = int(ai_length.get())
        note_dur = float(ai_note_dur.get())
    except Exception:
        messagebox.showerror('Invalid input', 'Enter numeric values for length and note duration')
        return
    melody = generate_ai_melody(length)
    freqs = melody_to_frequencies(melody)
    volume = 0.7
    instrument = 'piano'
    full = np.array([], dtype=np.float32)
    for f in freqs:
        t = generate_tone(f, note_dur, volume, 'sine', SAMPLE_RATE, instrument=instrument)
        full = np.concatenate([full, t])
    wav_file = 'ai_melody.wav'
    wav_path = save_wav(wav_file, full)
    play_wav_nonblocking(wav_path)
    visualize_waveform(full)

Button(frame_ai, text='🤖 AI Compose & Play', command=_ai_generate_and_play, bg='#00c8ff').grid(row=2, column=0, columnspan=4, pady=8)

# Emotion buttons
frame_emotion = Frame(root, bg='#2e003e')
frame_emotion.pack(pady=6)
Label(frame_emotion, text='Emotional Music', bg='#2e003e', fg='white').pack()


def _play_emotion(emotion):
    melody = generate_emotional_melody(emotion, length=16)
    freqs = melody_to_frequencies(melody)
    instrument = 'piano' if emotion in ['happy','romantic'] else 'flute'
    full = np.array([], dtype=np.float32)
    for f in freqs:
        t = generate_tone(f, 0.35, 0.75, 'sine', SAMPLE_RATE, instrument=instrument)
        full = np.concatenate([full, t])
    wav_file = f'{emotion}_music.wav'
    wav_path = save_wav(wav_file, full)
    play_wav_nonblocking(wav_path)
    visualize_waveform(full)

Button(frame_emotion, text='😊 Happy', command=lambda: _play_emotion('happy'), bg='#33ff77').pack(side=LEFT, padx=6)
Button(frame_emotion, text='😢 Sad', command=lambda: _play_emotion('sad'), bg='#ff6666').pack(side=LEFT, padx=6)
Button(frame_emotion, text='💖 Romantic', command=lambda: _play_emotion('romantic'), bg='#ff99cc').pack(side=LEFT, padx=6)
Button(frame_emotion, text='😱 Suspense', command=lambda: _play_emotion('suspense'), bg='#ffcc00').pack(side=LEFT, padx=6)

# Beat / Drum controls
frame_beat = Frame(root, bg='#2e003e')
frame_beat.pack(pady=8)
Label(frame_beat, text='Beat Generator', bg='#2e003e', fg='white').grid(row=0, column=0, columnspan=4)

Label(frame_beat, text='Tempo (BPM):', bg='#2e003e', fg='white').grid(row=1, column=0)
beat_tempo = Entry(frame_beat, width=6, bg='#4b0082', fg='white')
beat_tempo.grid(row=1, column=1)
beat_tempo.insert(0,'100')

Label(frame_beat, text='Pattern (comma separated):', bg='#2e003e', fg='white').grid(row=1, column=2)
pattern_entry = Entry(frame_beat, width=20, bg='#4b0082', fg='white')
pattern_entry.grid(row=1, column=3)
pattern_entry.insert(0,'kick,snare,kick,snare')


def _play_beat():
    try:
        tempo = int(beat_tempo.get())
    except Exception:
        messagebox.showerror('Invalid input', 'Enter numeric tempo')
        return
    pattern = [p.strip() for p in pattern_entry.get().split(',') if p.strip()]
    beat_audio = generate_beat(pattern, tempo)
    wav_file = 'beat.wav'
    wav_path = save_wav(wav_file, beat_audio)
    play_wav_nonblocking(wav_path)

Button(frame_beat, text='🥁 Play Beat', command=_play_beat, bg='#ffaa00').grid(row=2, column=0, columnspan=4, pady=8)

# Visualizer controls for last generated audio
frame_vis = Frame(root, bg='#2e003e')
frame_vis.pack(pady=6)
Label(frame_vis, text='Visualizer', bg='#2e003e', fg='white').pack()

# Export last generated file as MP3 convenience function

def _export_last_wav_to_mp3():
    wav_path = filedialog.askopenfilename(filetypes=[('WAV files','*.wav')], title='Select WAV to convert')
    if not wav_path:
        return
    if not pydub_available or not shutil.which('ffmpeg'):
        messagebox.showerror('Missing dependency', 'pydub and ffmpeg are required for MP3 export.')
        return
    mp3_path = filedialog.asksaveasfilename(defaultextension='.mp3', filetypes=[('MP3','*.mp3')])
    if not mp3_path:
        return
    try:
        wav_to_mp3(wav_path, mp3_path, bitrate=bitrate_box.get())
        messagebox.showinfo('Saved', f'MP3 saved to {mp3_path}')
    except Exception as e:
        messagebox.showerror('Export failed', str(e))

Button(frame_vis, text='Export WAV -> MP3', command=_export_last_wav_to_mp3, bg='#99ccff').pack(pady=6)

# Quick status info
status = 'ffmpeg found' if shutil.which('ffmpeg') else 'ffmpeg NOT found'
status += ' | pydub ' + ('available' if pydub_available else 'missing')
status += ' | playsound ' + ('available' if playsound else 'missing')
status += ' | matplotlib ' + ('available' if mpl_available else 'missing')
Label(root, text=status, bg='#2e003e', fg='lightyellow').pack(pady=6)

# Help / tips
help_text = (
    'Tips:\n- Install ffmpeg for MP3 export.\n- For non-blocking playback, install playsound (pip install playsound==1.2.2) or run on Windows.\n- Use the AI Composer to auto-generate melodies; visualize to see waveform.'
)
Label(root, text=help_text, bg='#2e003e', fg='white', justify=LEFT).pack(pady=6)

# Start GUI
root.mainloop()
