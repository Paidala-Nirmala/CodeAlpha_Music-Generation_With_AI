from transformers import AutoProcessor, MusicgenForConditionalGeneration
import scipy.io.wavfile
import torch

print("Loading AI model... (this may take 1–2 minutes)")

# Load the model
processor = AutoProcessor.from_pretrained("facebook/musicgen-small")
model = MusicgenForConditionalGeneration.from_pretrained("facebook/musicgen-small")

# Write your text
text = "a calm relaxing melody with piano and soft background ambience"

# Convert text to tokens
inputs = processor(
    text=[text],
    padding=True,
    return_tensors="pt"
)

print("Generating music...")

# Generate audio
audio_values = model.generate(**inputs, max_new_tokens=256)

# Convert to numpy
audio = audio_values[0, 0].cpu().numpy()

# Save output
output_file = "outputs/generated_music.wav"
scipy.io.wavfile.write(output_file, rate=model.config.audio_encoder.sampling_rate, data=audio)

print(f"Music generated and saved at: {output_file}")
