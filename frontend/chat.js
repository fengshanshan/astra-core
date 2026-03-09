const API_BASE = "";

const wechatSection = document.getElementById("wechat-section");
const birthSection = document.getElementById("birth-section");
const chatSection = document.getElementById("chat-section");
const wechatForm = document.getElementById("wechat-form");
const birthForm = document.getElementById("birth-form");
const chatForm = document.getElementById("chat-form");
const wechatInput = document.getElementById("wechat-id");
const messagesEl = document.getElementById("messages");
const messageInput = document.getElementById("message-input");
const loadingEl = document.getElementById("loading");
const loadingText = document.getElementById("loading-text");
const currentUserEl = document.getElementById("current-user");
const chartSummaryEl = document.getElementById("chart-summary");
const placeSearch = document.getElementById("place-search");
const searchBtn = document.getElementById("search-btn");
const mapContainer = document.getElementById("map-container");
const selectedPlaceEl = document.getElementById("selected-place");
const selectedPlaceText = document.getElementById("selected-place-text");
const clearPlaceBtn = document.getElementById("clear-place");
const backLink = document.getElementById("back-link");

let wechatId = null;
let selectedLocation = null;
let map = null;
let marker = null;

const NOMINATIM_HEADERS = {
  "Accept": "application/json",
  "User-Agent": "ChartService/1.0 (birthplace selector)",
};

function showLoading(show, text = "加载中...") {
  loadingText.textContent = text;
  loadingEl.classList.toggle("hidden", !show);
}

function showSection(section) {
  wechatSection.classList.add("hidden");
  birthSection.classList.add("hidden");
  chatSection.classList.add("hidden");
  section.classList.remove("hidden");
}

function updateBackLink() {
  if (backLink && wechatId) {
    backLink.href = `/?wechat_id=${encodeURIComponent(wechatId)}`;
  } else if (backLink) {
    backLink.href = "/";
  }
}

// ========== Map (复用 index 逻辑) ==========
function initMap() {
  if (map) return;
  map = L.map(mapContainer).setView([35, 105], 3);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "© OpenStreetMap",
  }).addTo(map);
  map.on("click", async (e) => {
    const { lat, lng } = e.latlng;
    setLocation(lat, lng, "获取中...");
    try {
      const name = await reverseGeocode(lat, lng);
      setLocation(lat, lng, name);
    } catch {
      setLocation(lat, lng, `${lat.toFixed(2)}°, ${lng.toFixed(2)}°`);
    }
  });
}

function setLocation(lat, lon, name) {
  selectedLocation = { lat, lon, name };
  selectedPlaceText.textContent = `已选: ${name}`;
  selectedPlaceEl.classList.remove("hidden");
  if (marker) map.removeLayer(marker);
  marker = L.marker([lat, lon]).addTo(map);
  map.setView([lat, lon], Math.max(map.getZoom(), 10));
}

clearPlaceBtn?.addEventListener("click", () => {
  selectedLocation = null;
  selectedPlaceEl.classList.add("hidden");
  if (marker) {
    map.removeLayer(marker);
    marker = null;
  }
});

async function reverseGeocode(lat, lon) {
  const url = `https://nominatim.openstreetmap.org/reverse?lat=${lat}&lon=${lon}&format=json`;
  const res = await fetch(url, { headers: NOMINATIM_HEADERS });
  if (!res.ok) throw new Error("Geocoding failed");
  const data = await res.json();
  const addr = data.address || {};
  const city = addr.city || addr.town || addr.village || addr.municipality || addr.county;
  const country = addr.country;
  if (city && country) return `${city}, ${country}`;
  if (city || country) return city || country;
  return data.display_name?.split(",").slice(0, 2).join(", ") || `${lat.toFixed(2)}°, ${lon.toFixed(2)}°`;
}

async function searchPlace(query) {
  const q = encodeURIComponent(query.trim());
  if (!q) return;
  const url = `https://nominatim.openstreetmap.org/search?q=${q}&format=json&limit=5`;
  const res = await fetch(url, { headers: NOMINATIM_HEADERS });
  if (!res.ok) throw new Error("搜索失败");
  const data = await res.json();
  if (!data.length) {
    alert("未找到该地点");
    return;
  }
  const first = data[0];
  setLocation(parseFloat(first.lat), parseFloat(first.lon), first.display_name);
}

searchBtn?.addEventListener("click", () => searchPlace(placeSearch.value));
placeSearch?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    searchPlace(placeSearch.value);
  }
});

const formObserver = new IntersectionObserver(
  ([entry]) => { if (entry.isIntersecting) initMap(); },
  { threshold: 0.1 }
);
formObserver.observe(birthSection);

// 页面加载时检查 URL 中的 wechat_id，若有则直接进入对话
(async function initFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const idFromUrl = params.get("wechat_id");
  if (!idFromUrl) return;

  showLoading(true, "加载用户...");
  try {
    const res = await fetch(`${API_BASE}/api/user/check?wechat_id=${encodeURIComponent(idFromUrl)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (!data.exists) return;

    wechatId = idFromUrl;
    updateBackLink();
    wechatInput.value = idFromUrl;
    showSection(chatSection);
    currentUserEl.textContent = `用户: ${idFromUrl}`;
    await loadAndDisplayChart();
    messageInput.focus();
  } catch {
    // 忽略错误
  } finally {
    showLoading(false);
  }
})();

// ========== Step 1: Wechat ID ==========
wechatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = wechatInput.value.trim();
  if (!id) return;

  showLoading(true, "验证用户...");
  try {
    const res = await fetch(`${API_BASE}/api/user/check?wechat_id=${encodeURIComponent(id)}`);
    if (!res.ok) throw new Error("请求失败");
    const data = await res.json();

    wechatId = id;
    updateBackLink();
    if (data.exists) {
      showSection(chatSection);
      currentUserEl.textContent = `用户: ${id}`;
      await loadAndDisplayChart();
      messageInput.focus();
    } else {
      document.getElementById("birth-wechat-display").textContent = `正在为「${id}」创建档案`;
      showSection(birthSection);
    }
  } catch (err) {
    alert(err.message || "请求失败，请稍后重试");
  } finally {
    showLoading(false);
  }
});

// ========== Step 2: 新建用户 - 出生信息 ==========
birthForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const date = document.getElementById("birth-date").value;
  const time = document.getElementById("birth-time").value;

  const body = {
    wechat_id: wechatId,
    date,
    time,
    latitude: selectedLocation?.lat ?? null,
    longitude: selectedLocation?.lon ?? null,
    place_name: selectedLocation?.name ?? null,
  };

  showLoading(true, "创建用户档案...");
  try {
    const res = await fetch(`${API_BASE}/api/user/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "注册失败");
    }
    showSection(chatSection);
    currentUserEl.textContent = `用户: ${wechatId}`;
    updateBackLink();
    await loadAndDisplayChart();
    messageInput.focus();
  } catch (err) {
    alert(err.message || "创建失败，请稍后重试");
  } finally {
    showLoading(false);
  }
});

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

async function loadAndDisplayChart() {
  if (!wechatId) return;
  try {
    const res = await fetch(`${API_BASE}/api/user/chart?wechat_id=${encodeURIComponent(wechatId)}`);
    if (!res.ok) return;
    const data = await res.json();
    if (data.chart_summary) {
      const rows = data.chart_summary.split("\n").filter(Boolean);
      chartSummaryEl.innerHTML = rows
        .map((line) => {
          const escaped = escapeHtml(line.replace(/\sR$/, ""));
          const retro = line.endsWith(" R") ? ' <span class="retrograde">R</span>' : "";
          return `<div class="planet-row">${escaped}${retro}</div>`;
        })
        .join("");
      chartSummaryEl.classList.remove("hidden");
    } else {
      chartSummaryEl.classList.add("hidden");
    }
  } catch {
    chartSummaryEl.classList.add("hidden");
  }
}

// ========== Step 3: 对话 ==========
function appendMessage(role, content) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = content;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = messageInput.value.trim();
  if (!message || !wechatId) return;

  appendMessage("user", message);
  messageInput.value = "";

  const submitBtn = chatForm.querySelector('button[type="submit"]');
  submitBtn.disabled = true;
  showLoading(true, "AI 正在思考...");

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wechat_id: wechatId, message }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "请求失败");
    }

    const data = await res.json();
    appendMessage("assistant", data.answer);
  } catch (err) {
    appendMessage("assistant", "抱歉，暂时无法回答。请稍后重试。");
  } finally {
    submitBtn.disabled = false;
    showLoading(false);
  }
});
