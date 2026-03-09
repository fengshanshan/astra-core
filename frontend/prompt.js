const API_BASE = "";

const promptForm = document.getElementById("prompt-form");
const promptContent = document.getElementById("prompt-content");
const statusEl = document.getElementById("status");
const loadingEl = document.getElementById("loading");

function showLoading(show) {
  loadingEl.classList.toggle("hidden", !show);
}

function showStatus(message, type) {
  statusEl.textContent = message;
  statusEl.className = "status " + (type || "");
  if (message) setTimeout(() => { statusEl.textContent = ""; statusEl.className = "status"; }, 4000);
}

async function loadPrompt() {
  showLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/prompt`);
    if (!res.ok) throw new Error("加载失败");
    const data = await res.json();
    promptContent.value = data.content || "";
  } catch (err) {
    showStatus(err.message || "加载失败，请稍后重试", "error");
  } finally {
    showLoading(false);
  }
}

promptForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const content = promptContent.value.trim();
  const submitBtn = promptForm.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  statusEl.textContent = "";
  statusEl.className = "status";

  try {
    const res = await fetch(`${API_BASE}/api/prompt`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "保存失败");
    }
    showStatus("保存成功，已生效", "success");
  } catch (err) {
    showStatus(err.message || "保存失败，请稍后重试", "error");
  } finally {
    submitBtn.disabled = false;
  }
});

loadPrompt();
