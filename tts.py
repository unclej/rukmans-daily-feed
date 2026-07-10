import sys
import os
import re
from kokoro_onnx import Kokoro
import soundfile as sf

if len(sys.argv) < 3:
    print("Usage: tts.py <text> <output_path>")
    sys.exit(1)

text = sys.argv[1]
output_path = sys.argv[2]

# Replace periods between digits with " point " so version numbers like
# "5.4" or "GPT-4.1" aren't split into separate sentences by the TTS engine
text = re.sub(r'(?<=\d)\.(?=\d)', ' point ', text)

model_dir = os.path.expanduser("./kokoro")
k = Kokoro(
    os.path.join(model_dir, "kokoro-v1.0.onnx"),
    os.path.join(model_dir, "voices-v1.0.bin")
)

samples, rate = k.create(text, voice="af_sarah", speed=1.0, lang="en-us")
sf.write(output_path, samples, rate)
print(f"Saved to {output_path}")
