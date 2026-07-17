const appEl = document.getElementById("participant-app");
const connEl = document.getElementById("connection");
let ws;
let reconnectTimer;
let lastStateSignature = "";

function money(value) {
  return value == null ? "-" : `T$ ${Number(value).toLocaleString("pt-BR")}`;
}

function setConn(text, cls) {
  connEl.textContent = text;
  connEl.className = `connection ${cls || ""}`;
}

async function loadState(force = false) {
  try {
    const res = await fetch("/api/current-state", { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) {
      location.href = "/";
      return;
    }
    const state = await res.json();
    const signature = JSON.stringify(state);
    if (force || signature !== lastStateSignature) {
      lastStateSignature = signature;
      render(state);
    }
  } catch (error) {
    setConn("reconectando", "warn");
  }
}

function render(state) {
  const p = state.participant;
  if (!state.item) {
    appEl.className = "item-card empty";
    appEl.innerHTML = `<div class="item-image logo-waiting"><img src="/static/uploads/logo2026.png" alt="Leilão Calebe"></div><h2>Aguardando o próximo item.</h2><p>Você será avisado automaticamente quando uma rodada iniciar.</p>`;
    return;
  }
  const disabled = p.status !== "available";
  const reason = p.status === "winner" ? "Você já ganhou um item e não pode participar das próximas rodadas." : p.status === "blocked" ? "Sua participação está bloqueada." : "";
  const confirmed = Boolean(state.my_bid);
  appEl.className = `item-card ${confirmed ? "confirmed" : ""}`;
  appEl.innerHTML = `
    <div class="item-image">${state.item.image_path ? `<img src="${state.item.image_path}" alt="">` : `<img src="/static/uploads/logo2026.png" alt="Leilão Calebe">`}</div>
    <span class="position">${state.item.position || ""}</span>
    <h1>${state.item.name}</h1>
    <p>${state.item.description || ""}</p>
    <div class="value-box">Seu valor fictício: <strong>${p.fixed_value_label}</strong></div>
    ${confirmed ? `<div class="alert success">Participação confirmada com ${money(state.my_bid.value)}.</div>` : ""}
    ${reason ? `<div class="alert warn">${reason}</div>` : ""}
    <div class="choice-actions ${confirmed ? "confirmed-actions" : ""}">
      ${confirmed ? `<button id="cancel-btn" class="btn no-btn">NÃO QUERO MAIS</button>` : `<button id="bid-btn" class="btn want-btn" ${disabled ? "disabled" : ""}>EU QUERO</button><button id="no-btn" class="btn no-btn">NÃO QUERO</button>`}
    </div>
  `;
  document.getElementById("bid-btn")?.addEventListener("click", placeBid);
  document.getElementById("no-btn")?.addEventListener("click", () => loadState(true));
  document.getElementById("cancel-btn")?.addEventListener("click", cancelBid);
}

async function placeBid() {
  const btn = document.getElementById("bid-btn");
  btn.disabled = true;
  btn.textContent = "Confirmando...";
  const res = await fetch("/api/bid", { method: "POST", credentials: "same-origin" });
  if (!res.ok) alert((await res.json()).detail || "Não foi possível confirmar.");
  await loadState(true);
}

async function cancelBid() {
  const res = await fetch("/api/bid", { method: "DELETE", credentials: "same-origin" });
  if (!res.ok) alert((await res.json()).detail || "Não foi possível cancelar.");
  await loadState(true);
}

function connect() {
  clearTimeout(reconnectTimer);
  setConn("reconectando", "warn");
  ws = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/participant`);
  ws.onopen = () => { setConn("conectado", "ok"); loadState(true); };
  ws.onmessage = () => loadState(true);
  ws.onclose = () => {
    setConn("conexão perdida", "bad");
    reconnectTimer = setTimeout(connect, 1500);
  };
  ws.onerror = () => ws.close();
}

connect();
loadState(true);
setInterval(() => loadState(false), 2000);
setInterval(() => {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send("ping");
}, 25000);