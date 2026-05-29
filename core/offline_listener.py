import sounddevice as sd
from scipy.io.wavfile import write
from faster_whisper import WhisperModel
import tempfile

model = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)


def listen_offline():
    fs = 16000
    duration = 8

    print("Listening for command... speak clearly")

    recording = sd.rec(
        int(duration * fs),
        samplerate=fs,
        channels=1,
        dtype="int16"
    )

    sd.wait()

    temp_wav = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)

    write(temp_wav.name, fs, recording)

    segments, info = model.transcribe(
        temp_wav.name,
        language="en",
        beam_size=5,
        vad_filter=True,
        condition_on_previous_text=False
    )

    text = ""

    for segment in segments:
        text += segment.text + " "

    text = text.lower().strip()

    print("Whisper heard:", text)

    return text