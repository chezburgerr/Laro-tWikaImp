let currentWordIndex = 0;
let modalWords = [];

function updateWordDisplay() {
  const wordDisplay = document.getElementById("wordDisplay");
  wordDisplay.textContent = modalWords[currentWordIndex] || "No words";

  document.getElementById("modalPrevBtn").disabled = currentWordIndex === 0;
  document.getElementById("modalNextBtn").disabled = currentWordIndex === modalWords.length - 1;
}

document.querySelectorAll(".level-button").forEach(btn => {
  btn.addEventListener("click", async () => {
    const level = btn.dataset.level;
    const lesson = "{{ selected_lesson }}";

    try {
      const res = await fetch(`/api/level-words?level=${level}&lesson=${lesson}`);
      const data = await res.json();

      document.getElementById("modalLevel").textContent = level;

      // Store words and reset index
      modalWords = data.words;
      currentWordIndex = 0;

      // Show first word
      updateWordDisplay();

      // Show modal
      document.getElementById("wordModal").style.display = "block";

      // Proceed button behavior
      const proceedBtn = document.getElementById("proceedBtn");
      proceedBtn.onclick = () => {
        window.location.href = `/level?level=${level}&lesson=${lesson}`;
      };

    } catch (err) {
      alert("⚠️ Failed to load words.");
    }
  });
});

document.getElementById("closeModal").onclick = () => {
  document.getElementById("wordModal").style.display = "none";
};

document.getElementById("modalPrevBtn").addEventListener("click", () => {
  if (currentWordIndex > 0) {
    currentWordIndex--;
    updateWordDisplay();
  }
});

document.getElementById("modalNextBtn").addEventListener("click", () => {
  if (currentWordIndex < modalWords.length - 1) {
    currentWordIndex++;
    updateWordDisplay();
  }
});

// Optional: Keyboard navigation
document.addEventListener("keydown", e => {
  if (document.getElementById("wordModal").style.display === "block") {
    if (e.key === "ArrowRight") document.getElementById("modalNextBtn").click();
    if (e.key === "ArrowLeft") document.getElementById("modalPrevBtn").click();
  }
});