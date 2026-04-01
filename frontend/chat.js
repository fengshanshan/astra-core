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
const conversationSelect = document.getElementById("conversation-select");
const newConversationBtn = document.getElementById("new-conversation-btn");
const placeSearch = document.getElementById("place-search");
const searchBtn = document.getElementById("search-btn");
const cityResultsEl = document.getElementById("city-results");
const selectedPlaceEl = document.getElementById("selected-place");
const selectedPlaceText = document.getElementById("selected-place-text");
const clearPlaceBtn = document.getElementById("clear-place");
const cityHintEl = document.getElementById("city-hint");
const manualLatInput = document.getElementById("manual-lat");
const manualLngInput = document.getElementById("manual-lng");
const manualPlaceNameInput = document.getElementById("manual-place-name");
const manualApplyBtn = document.getElementById("manual-apply-btn");

let wechatId = null;
let selectedLocation = null;
let currentConversationId = null;
/** 服务端是否配置了 AMAP_KEY（未配置则禁用搜索） */
let geoSearchAvailable = false;

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

// ========== 出生地：城市搜索（经纬度 → 后端 timezonefinder 判时区）==========
async function initGeoSearchAvailability() {
  try {
    const cfg = await fetch(`${API_BASE}/api/geo/config`).then((r) => r.json());
    geoSearchAvailable = !!cfg.amap;
  } catch {
    geoSearchAvailable = false;
  }
  if (!placeSearch || !searchBtn) return;
  const searchPanel = document.querySelector(".city-panel-search");
  if (!geoSearchAvailable) {
    placeSearch.disabled = true;
    searchBtn.disabled = true;
    placeSearch.placeholder = "未配置高德 Key，无法搜索";
    searchPanel?.classList.add("city-panel-search--disabled");
    if (cityHintEl) {
      cityHintEl.textContent =
        "未配置高德 Key 时无法搜索，请用手动经纬度兜底，或跳过出生地（使用中国时区）。";
    }
  } else {
    searchPanel?.classList.remove("city-panel-search--disabled");
  }
}

initGeoSearchAvailability();

function setLocation(lat, lon, name) {
  selectedLocation = { lat, lon, name };
  selectedPlaceText.textContent = `已选: ${name}（${lat.toFixed(2)}°, ${lon.toFixed(2)}°）`;
  selectedPlaceEl.classList.remove("hidden");
  cityResultsEl.classList.add("hidden");
  cityResultsEl.innerHTML = "";
  if (manualLatInput) manualLatInput.value = String(lat);
  if (manualLngInput) manualLngInput.value = String(lon);
  if (manualPlaceNameInput) {
    manualPlaceNameInput.value = name === "手动坐标" ? "" : name;
  }
}

function applyManualCoordinates() {
  const latStr = manualLatInput?.value?.trim() ?? "";
  const lngStr = manualLngInput?.value?.trim() ?? "";
  if (!latStr || !lngStr) {
    alert("请填写纬度与经度");
    return;
  }
  const lat = Number(latStr);
  const lon = Number(lngStr);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    alert("经纬度必须是数字");
    return;
  }
  if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
    alert("纬度需在 -90～90，经度需在 -180～180");
    return;
  }
  const note = (manualPlaceNameInput?.value ?? "").trim();
  const name = note || "手动坐标";
  setLocation(lat, lon, name);
}

function renderCityResults(results) {
  cityResultsEl.innerHTML = "";
  results.forEach((r) => {
    const li = document.createElement("li");
    li.className = "city-result-item";
    li.setAttribute("role", "option");
    li.dataset.lat = String(r.lat);
    li.dataset.lng = String(r.lng);
    li.dataset.name = r.name || "";
    li.textContent = `${r.name} · ${Number(r.lat).toFixed(2)}°, ${Number(r.lng).toFixed(2)}°`;
    li.addEventListener("click", () => {
      setLocation(r.lat, r.lng, r.name);
    });
    cityResultsEl.appendChild(li);
  });
  cityResultsEl.classList.toggle("hidden", results.length === 0);
}

clearPlaceBtn?.addEventListener("click", () => {
  selectedLocation = null;
  selectedPlaceEl.classList.add("hidden");
  cityResultsEl.classList.add("hidden");
  cityResultsEl.innerHTML = "";
  if (manualLatInput) manualLatInput.value = "";
  if (manualLngInput) manualLngInput.value = "";
  if (manualPlaceNameInput) manualPlaceNameInput.value = "";
});

manualApplyBtn?.addEventListener("click", () => {
  applyManualCoordinates();
});
[manualLatInput, manualLngInput, manualPlaceNameInput].forEach((el) => {
  el?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      applyManualCoordinates();
    }
  });
});

async function searchPlace(query) {
  const q = query.trim();
  if (!q) return;
  if (!geoSearchAvailable) {
    alert("未配置 AMAP_KEY，无法搜索地点");
    return;
  }
  const url = `${API_BASE}/api/geo/search?q=${encodeURIComponent(q)}&city_only=true`;
  const res = await fetch(url);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert(err.detail || "搜索失败");
    return;
  }
  const data = await res.json();
  const results = data.results || [];
  if (!results.length) {
    alert("未找到该城市，请换关键词试试");
    cityResultsEl.classList.add("hidden");
    cityResultsEl.innerHTML = "";
    return;
  }
  renderCityResults(results);
}

searchBtn?.addEventListener("click", () => {
  searchPlace(placeSearch.value).catch((e) => alert(e.message || "搜索失败"));
});
placeSearch?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    searchPlace(placeSearch.value).catch((err) => alert(err.message || "搜索失败"));
  }
});

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
    wechatInput.value = idFromUrl;
    showSection(chatSection);
    currentUserEl.textContent = `用户: ${idFromUrl}`;
    await loadAndDisplayChart();
    await ensureConversationReady();
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
    if (data.exists) {
      showSection(chatSection);
      currentUserEl.textContent = `用户: ${id}`;
      await loadAndDisplayChart();
      await ensureConversationReady();
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
    await loadAndDisplayChart();
    await ensureConversationReady();
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

function clearMessages() {
  messagesEl.innerHTML = "";
}

function conversationOptionLabel(c, idx) {
  const iso = c.updated_at || c.created_at;
  if (iso) {
    const d = new Date(iso);
    if (!Number.isNaN(d.getTime())) {
      return d.toLocaleString("zh-CN", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    }
  }
  return `会话 ${idx + 1}`;
}

function renderConversationOptions(conversations) {
  conversationSelect.innerHTML = "";
  if (!conversations.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "暂无会话";
    conversationSelect.appendChild(opt);
    conversationSelect.disabled = true;
    return;
  }
  conversationSelect.disabled = false;
  conversations.forEach((c, idx) => {
    const opt = document.createElement("option");
    opt.value = c.id;
    opt.textContent = conversationOptionLabel(c, idx);
    conversationSelect.appendChild(opt);
  });
}

async function fetchConversations() {
  const res = await fetch(`${API_BASE}/api/conversations?wechat_id=${encodeURIComponent(wechatId)}`);
  if (!res.ok) throw new Error("获取会话失败");
  return await res.json();
}

async function createConversation() {
  const res = await fetch(`${API_BASE}/api/conversations`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ wechat_id: wechatId }),
  });
  if (!res.ok) throw new Error("新建会话失败");
  return await res.json();
}

async function fetchConversationMessages(conversationId) {
  const res = await fetch(
    `${API_BASE}/api/conversations/${encodeURIComponent(conversationId)}/messages?wechat_id=${encodeURIComponent(wechatId)}`
  );
  if (!res.ok) throw new Error("获取会话消息失败");
  return await res.json();
}

async function switchConversation(conversationId) {
  currentConversationId = conversationId;
  clearMessages();
  if (!conversationId) return;
  showLoading(true, "加载会话...");
  try {
    const msgs = await fetchConversationMessages(conversationId);
    msgs.forEach((m) => {
      if (m.role === "user" || m.role === "assistant") {
        appendMessage(m.role, m.content);
      }
    });
  } finally {
    showLoading(false);
  }
}

async function ensureConversationReady() {
  // 进入 chat 页面时：默认开启新对话（与主流产品一致），历史会话仍可从下拉框切换
  const convs = await fetchConversations().catch(() => []);
  renderConversationOptions(convs);

  const created = await createConversation();
  // 直接追加到下拉框并切换到新会话，避免排序/刷新导致选择错乱
  const opt = document.createElement("option");
  opt.value = created.id;
  opt.textContent = conversationOptionLabel(created, conversationSelect.options.length);
  conversationSelect.appendChild(opt);
  conversationSelect.disabled = false;
  conversationSelect.value = created.id;
  await switchConversation(created.id);
}

// ========== Step 3: 对话 ==========
function appendMessage(role, content) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  div.textContent = content;
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function appendTypingIndicator() {
  const div = document.createElement("div");
  div.className = "message assistant typing";
  div.dataset.typing = "1";
  div.innerHTML = '<span class="typing-dots"><span></span><span></span><span></span></span>';
  messagesEl.appendChild(div);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return div;
}

function replaceTypingWithContent(typingEl, content) {
  typingEl.classList.remove("typing");
  typingEl.removeAttribute("data-typing");
  typingEl.textContent = content;
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

chatForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const message = messageInput.value.trim();
  if (!message || !wechatId) return;
  if (!currentConversationId) {
    // 正常情况下不会发生（进入 chat 会创建/选择会话），兜底：先创建会话再发送
    try {
      const created = await createConversation();
      const convs = await fetchConversations();
      renderConversationOptions(convs);
      conversationSelect.value = created.id;
      await switchConversation(created.id);
    } catch {
      // ignore; will fail below
    }
  }

  appendMessage("user", message);
  messageInput.value = "";

  const submitBtn = chatForm.querySelector('button[type="submit"]');
  submitBtn.disabled = true;

  const typingEl = appendTypingIndicator();

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ wechat_id: wechatId, message, conversation_id: currentConversationId }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || "请求失败");
    }

    const data = await res.json();
    if (data.conversation_id && data.conversation_id !== currentConversationId) {
      // 后端可能创建了新会话：同步前端状态并刷新会话列表
      currentConversationId = data.conversation_id;
      const convs = await fetchConversations().catch(() => null);
      if (convs) {
        renderConversationOptions(convs);
        conversationSelect.value = currentConversationId;
      }
    }
    replaceTypingWithContent(typingEl, data.answer);
    if (data.suggest_new_conversation) {
      showNewConversationSuggestion();
    }
  } catch (err) {
    replaceTypingWithContent(typingEl, "抱歉，暂时无法回答。请稍后重试。");
  } finally {
    submitBtn.disabled = false;
  }
});

function showNewConversationSuggestion() {
  // 避免重复显示
  if (document.getElementById("new-conv-suggestion")) return;
  const card = document.createElement("div");
  card.id = "new-conv-suggestion";
  card.className = "new-conv-suggestion";
  card.innerHTML = `
    <span class="new-conv-icon">✨</span>
    <div class="new-conv-text">
      <div class="new-conv-title">这个话题已经告一段落～</div>
      <div class="new-conv-subtitle">想聊新的困惑，可以开启一段新对话</div>
    </div>
    <button class="new-conv-btn" id="new-conv-suggestion-btn">开启新对话</button>
  `;
  messagesEl.appendChild(card);
  messagesEl.scrollTop = messagesEl.scrollHeight;

  document.getElementById("new-conv-suggestion-btn").addEventListener("click", async () => {
    card.remove();
    newConversationBtn.click();
  });
}

conversationSelect?.addEventListener("change", async () => {
  const id = conversationSelect.value;
  await switchConversation(id);
});

newConversationBtn?.addEventListener("click", async () => {
  if (!wechatId) return;
  showLoading(true, "新建会话...");
  try {
    const created = await createConversation();
    // 直接追加到下拉框并切换到新会话，避免排序/刷新导致选择错乱
    const opt = document.createElement("option");
    opt.value = created.id;
    opt.textContent = conversationOptionLabel(created, conversationSelect.options.length);
    conversationSelect.appendChild(opt);
    conversationSelect.disabled = false;
    conversationSelect.value = created.id;
    await switchConversation(created.id);
    messageInput.focus();
  } catch (err) {
    alert(err.message || "新建会话失败");
  } finally {
    showLoading(false);
  }
});
