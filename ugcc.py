import os
from flask import Flask, request, jsonify,send_from_directory, render_template
from faster_whisper import WhisperModel
from flask_cors import CORS
import subprocess
import wave
import webrtcvad

app = Flask(__name__, static_folder="./static", template_folder="./templates")
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

print("🔄 Loading Whisper model (large)...")
model = WhisperModel("large")
print("✅ Whisper model loaded.")

def format_timestamp(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

def extract_audio_from_mp4(mp4_path, wav_path):
    print(f"🎵 Extracting audio from {mp4_path} to {wav_path}...")
    command = [
        "ffmpeg", "-y", "-i", mp4_path,
        "-ac", "1", "-ar", "16000", wav_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("✅ Audio extraction complete.")

def read_wave(path):
    with wave.open(path, "rb") as wf:
        sample_rate = wf.getframerate()
        pcm_data = wf.readframes(wf.getnframes())
    print(f"🎧 Loaded WAV audio from {path} (Sample rate: {sample_rate} Hz).")
    return pcm_data, sample_rate

def write_wave(path, audio, sample_rate):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio)
    print(f"💾 Cleaned audio written to {path}.")

def frame_generator(frame_duration_ms, audio, sample_rate):
    n = int(sample_rate * (frame_duration_ms / 1000.0) * 2)
    offset = 0
    while offset + n < len(audio):
        yield audio[offset:offset + n]
        offset += n

def vad_collector(sample_rate, frame_duration_ms, padding_duration_ms, vad, frames):
    num_padding_frames = int(padding_duration_ms / frame_duration_ms)
    ring_buffer = []
    triggered = False
    voiced_frames = []

    for frame in frames:
        is_speech = vad.is_speech(frame, sample_rate)

        if not triggered:
            ring_buffer.append(frame)
            if len(ring_buffer) > num_padding_frames:
                ring_buffer.pop(0)
            if sum(vad.is_speech(f, sample_rate) for f in ring_buffer) > 0.9 * len(ring_buffer):
                triggered = True
                voiced_frames.extend(ring_buffer)
                ring_buffer = []
        else:
            voiced_frames.append(frame)
            ring_buffer.append(frame)
            if len(ring_buffer) > num_padding_frames:
                ring_buffer.pop(0)
            if sum(vad.is_speech(f, sample_rate) for f in ring_buffer) < 0.1 * len(ring_buffer):
                triggered = False
                yield b"".join(voiced_frames)
                ring_buffer = []
                voiced_frames = []

    if voiced_frames:
        yield b"".join(voiced_frames)

@app.route("/transcribe", methods=["POST"])
def transcribe():
    print("📥 Received transcription request.")

    if "file" not in request.files:
        print("⚠️ No file part in request.")
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        print("⚠️ No file selected.")
        return jsonify({"error": "Empty filename"}), 400

    filename = file.filename
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    print(f"💾 Saving uploaded file to {filepath}...")
    file.save(filepath)
    print("✅ File saved.")

    wav_path = os.path.join(UPLOAD_FOLDER, "temp.wav")
    cleaned_wav_path = os.path.join(UPLOAD_FOLDER, "cleaned.wav")
    srt_path = os.path.join(UPLOAD_FOLDER, "transcription.srt")

    extract_audio_from_mp4(filepath, wav_path)

    audio, sample_rate = read_wave(wav_path)

    print("🎤 Running Voice Activity Detection (VAD)...")
    vad = webrtcvad.Vad(2)# make more agro /////////////////////////////
    frames = list(frame_generator(30, audio, sample_rate))
    segments = list(vad_collector(sample_rate, 30, 300, vad, frames))
    print(f"✅ VAD complete. {len(segments)} speech segments found.")

    cleaned_audio = b"".join(segments)
    write_wave(cleaned_wav_path, cleaned_audio, sample_rate)

    print("🔊 Transcribing cleaned audio with Whisper...")
    segments, _ = model.transcribe(cleaned_wav_path, word_timestamps=True)

    CONFIDENCE_THRESHOLD = 0.7
    srt_output = ""
    index = 1
    for segment in segments:
        words = segment.words
        if not words:
            continue
        avg_confidence = sum(word.probability for word in words) / len(words)
        if avg_confidence < CONFIDENCE_THRESHOLD:
            continue

        start = format_timestamp(segment.start)
        end = format_timestamp(segment.end)
        text = segment.text.strip()

        srt_output += f"{index}\n{start} --> {end}\n{text}\n\n"
        index += 1

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write(srt_output)

    print(f"✅ SRT file saved at: {srt_path}")
    return jsonify({"message": "Transcription complete and SRT saved."}), 200

@app.route("/get-srt", methods=["GET"])
def get_srt():
    srt_path = os.path.join(UPLOAD_FOLDER, "transcription.srt")
    if not os.path.exists(srt_path):
        return jsonify({"error": "SRT file not found"}), 404

    print("📤 Serving SRT file content to frontend.")
    with open(srt_path, "r", encoding="utf-8") as f:
        srt_content = f.read()

    return srt_content, 200, {"Content-Type": "text/plain; charset=utf-8"}

@app.route('/download')
def download_srt():
    return send_from_directory(
        directory='uploads',       # Relative folder
        path='transcription.srt',      # File name
        as_attachment=True         # Forces download
    )


if __name__ == "__main__":
    print("🚀 Starting Flask app on http://localhost:5000")
    app.run(debug=True)
