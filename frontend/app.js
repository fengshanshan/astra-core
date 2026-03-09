// API base - use relative path when served from same origin
const API_BASE = "";

const formSection = document.getElementById("form-section");
const chatLink = document.getElementById("chat-link");
const chatSection = document.getElementById("chat-section");
const birthForm = document.getElementById("birth-form");
const chatForm = document.getElementById("chat-form");
const messagesEl = document.getElementById("messages");
const chartSummaryEl = document.getElementById("chart-summary");
const questionInput = document.getElementById("question");
const loadingEl = document.getElementById("loading");
const placeSearch = document.getElementById("place-search");
const searchBtn = document.getElementById("search-btn");
const mapContainer = document.getElementById("map-container");
const selectedPlaceEl = document.getElementById("selected-place");
const selectedPlaceText = document.getElementById("selected-place-text");
const clearPlaceBtn = document.getElementById("clear-place");
const backBtn = document.getElementById("back-btn");

let birthData = null;
let selectedLocation = null; // { lat, lon, name }
let map = null;
let marker = null;

const NOMINATIM_HEADERS = {
  "Accept": "application/json",
  "User-Agent": "ChartService/1.0 (birthplace selector)",
};

// Initialize map
function initMap() {
  if (map) return;
  map = L.map(mapContainer).setView([35, 105], 3); // Center on China
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

// Nominatim reverse geocode - 返回简短地点名
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

// Nominatim search
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
  const lat = parseFloat(first.lat);
  const lon = parseFloat(first.lon);
  const name = first.display_name;
  setLocation(lat, lon, name);
}

searchBtn.addEventListener("click", () => searchPlace(placeSearch.value));
placeSearch.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    searchPlace(placeSearch.value);
  }
});

// 根据用户数据预填出生信息表单
function preFillBirthForm(birthData) {
  if (!birthData) return;
  const dateInput = document.getElementById("date");
  const timeInput = document.getElementById("time");
  if (dateInput && birthData.date) dateInput.value = birthData.date;
  if (timeInput && birthData.time) timeInput.value = birthData.time;
  if (birthData.latitude != null && birthData.longitude != null) {
    initMap();
    const name = `${birthData.latitude.toFixed(2)}°, ${birthData.longitude.toFixed(2)}°`;
    setLocation(birthData.latitude, birthData.longitude, name);
  }
}

// 页面加载时检查 URL 中的 wechat_id，若有则加载用户星盘
(async function initFromUrl() {
  const params = new URLSearchParams(window.location.search);
  const wechatIdFromUrl = params.get("wechat_id");
  if (!wechatIdFromUrl) return;

  showLoading(true);
  try {
    const res = await fetch(`${API_BASE}/api/user/chart?wechat_id=${encodeURIComponent(wechatIdFromUrl)}`);
    if (!res.ok) {
      showLoading(false);
      return;
    }
    const data = await res.json();

    if (chatLink) chatLink.href = `/chat.html?wechat_id=${encodeURIComponent(wechatIdFromUrl)}`;

    if (data.birth_data && data.chart_snapshot?.planets && data.chart_snapshot?.ascendant) {
      birthData = data.birth_data;
      renderChartSummaryFromSnapshot(data.chart_snapshot);
      formSection.classList.add("hidden");
      chatSection.classList.remove("hidden");
      questionInput.focus();
    } else if (data.birth_data) {
      birthData = data.birth_data;
      preFillBirthForm(data.birth_data);
    }
  } catch {
    // 忽略错误，继续显示表单
  } finally {
    showLoading(false);
  }
})();

function renderChartSummaryFromSnapshot(snapshot) {
  if (!snapshot?.planets || !snapshot?.ascendant) return;
  const { planets, ascendant } = snapshot;
  const rows = Object.entries(planets).map(([name, p]) => {
    const retro = p.retrograde ? ' <span class="retrograde">R</span>' : "";
    const nameMap = {
      sun: "太阳", moon: "月亮", mercury: "水星", venus: "金星",
      mars: "火星", jupiter: "木星", saturn: "土星",
    };
    return `<div class="planet-row">${nameMap[name] || name}: ${p.sign} ${p.degree}° 第${p.house}宫${retro}</div>`;
  });
  rows.push(`<div class="planet-row">上升: ${ascendant.sign} ${ascendant.degree}°</div>`);
  chartSummaryEl.innerHTML = rows.join("");
}

// Lazy init map when form section is visible；若 URL 有 wechat_id 且表单未预填，则尝试拉取并预填
const formObserver = new IntersectionObserver(
  async ([entry]) => {
    if (!entry.isIntersecting) return;
    initMap();
    const wechatIdFromUrl = new URLSearchParams(window.location.search).get("wechat_id");
    if (wechatIdFromUrl && !birthData) {
      try {
        const res = await fetch(`${API_BASE}/api/user/chart?wechat_id=${encodeURIComponent(wechatIdFromUrl)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.birth_data) {
            birthData = data.birth_data;
            preFillBirthForm(data.birth_data);
          }
        }
      } catch {}
    }
  },
  { threshold: 0.1 }
);
formObserver.observe(formSection);

// Submit birth form
birthForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const date = document.getElementById("date").value;
  const time = document.getElementById("time").value;

  birthData = { date, time };
  if (selectedLocation) {
    birthData.latitude = selectedLocation.lat;
    birthData.longitude = selectedLocation.lon;
    birthData.placeName = selectedLocation.name;
  } else {
    birthData.latitude = null;
    birthData.longitude = null;
  }

  showLoading(true);
  try {
    const chartRes = await fetch(`${API_BASE}/api/calculate-chart`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(birthData),
    });
    if (!chartRes.ok) throw new Error("星盘计算失败");
    const chart = await chartRes.json();
    renderChartSummary(chart);
    formSection.classList.add("hidden");
    chatSection.classList.remove("hidden");
    questionInput.focus();
  } catch (err) {
    alert(err.message || "请求失败，请检查网络或稍后重试");
  } finally {
    showLoading(false);
  }
});

// Render chart summary
function renderChartSummary(chart) {
  const { planets, ascendant } = chart;
  const rows = Object.entries(planets).map(([name, p]) => {
    const retro = p.retrograde ? ' <span class="retrograde">R</span>' : "";
    const nameMap = {
      sun: "太阳", moon: "月亮", mercury: "水星", venus: "金星",
      mars: "火星", jupiter: "木星", saturn: "土星",
    };
    return `<div class="planet-row">${nameMap[name] || name}: ${p.sign} ${p.degree}° 第${p.house}宫${retro}</div>`;
  });
  rows.push(`<div class="planet-row">上升: ${ascendant.sign} ${ascendant.degree}°</div>`);
  if (birthData.placeName) {
    rows.push(`<div class="planet-row">出生地: ${birthData.placeName}</div>`);
  }
  chartSummaryEl.innerHTML = rows.join("");
}

// Send chat message
chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const question = questionInput.value.trim();
  if (!question) return;

  appendMessage("user", question);
  questionInput.value = "";
  const submitBtn = chatForm.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...birthData, question }),
    });
    if (!res.ok) throw new Error("请求失败");
    const data = await res.json();
    appendMessage("assistant", data.answer);
  } catch (err) {
    appendMessage("assistant", "抱歉，暂时无法回答。请稍后重试。");
  } finally {
    submitBtn.disabled = false;
  }
});

function appendMessage(role, content) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = content;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

// Back to form
backBtn.addEventListener("click", async () => {
  chatSection.classList.add("hidden");
  formSection.classList.remove("hidden");
  messagesEl.innerHTML = "";

  const wechatIdFromUrl = new URLSearchParams(window.location.search).get("wechat_id");
  if (wechatIdFromUrl && birthData) {
    preFillBirthForm(birthData);
  } else if (wechatIdFromUrl) {
    try {
      const res = await fetch(`${API_BASE}/api/user/chart?wechat_id=${encodeURIComponent(wechatIdFromUrl)}`);
      if (res.ok) {
        const data = await res.json();
        if (data.birth_data) {
          birthData = data.birth_data;
          preFillBirthForm(data.birth_data);
        }
      }
    } catch {}
  }
});

function showLoading(show) {
  loadingEl.classList.toggle("hidden", !show);
}
