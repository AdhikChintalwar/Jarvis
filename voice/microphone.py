import pyaudio


SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK = 1280
FORMAT = pyaudio.paInt16


def open_microphone_stream():
    audio = pyaudio.PyAudio()

    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK
    )

    return audio, stream
