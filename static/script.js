const uploadBtn = document.getElementById("upload-btn");
const fileInput = document.getElementById("video-file");
const output = document.getElementById("output");
const transcriptBox = document.getElementById("transcript");
const fetchBtn = document.getElementById("fetch-srt");
const downloadBtn = document.getElementById("download-srt");

downloadBtn.addEventListener("click", () => {
  window.location.href = "/download";
});


uploadBtn.addEventListener("click", async () => {
  const file = fileInput.files[0];
  if (!file) {
    alert("Please select an .mp4 file.");
    return;
  }

  output.textContent = "⏳ Uploading and transcribing...";

  const formData = new FormData();
  formData.append("file", file);

   await axios.post("http://localhost:5000/transcribe", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  })
  .then(response => {
    output.textContent = "✅ Transcription complete. You can now view the subtitles.";
    fetchBtn.disabled = false; // Enable the fetch button
  })
  .catch(error => {
    output.textContent = `❌ Error: ${error.response?.status || ''} ${error.message}`;
  });
});

fetchBtn.addEventListener("click", () => {
  output.textContent = "📄 Fetching subtitles...";

  axios.get("http://localhost:5000/get-srt")
    .then(response => {
      transcriptBox.textContent = response.data;
      output.textContent = "✅ Subtitles loaded.";
    })
    .catch(error => {
      output.textContent = "⚠️ Could not load subtitles: " + error.message;
    });
});

fetchBtn.addEventListener("click", () => {
  output.textContent = "📄 Fetching file...";

  axios.get("http://localhost:5000/get-srt")
    .then(response => {
      transcriptBox.textContent = response.data;
      output.textContent = "✅ Subtitles loaded.";
    })
    .catch(error => {
      output.textContent = "⚠️ Could not load subtitles: " + error.message;
    });
});