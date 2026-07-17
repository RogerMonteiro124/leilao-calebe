let adminWs;
let adminTimer;
let lastAdminSignature = "";

async function pollAdminState(force = false) {
  try {
    const res = await fetch("/admin/api/current-state", { credentials: "same-origin", cache: "no-store" });
    if (!res.ok) return;
    const state = await res.json();
    const signature = JSON.stringify(state);
    if (!lastAdminSignature) {
      lastAdminSignature = signature;
      return;
    }
    if (force || signature !== lastAdminSignature) {
      location.reload();
    }
  } catch (error) {
    // Polling is a fallback; the next interval will try again.
  }
}

function connectAdmin() {
  clearTimeout(adminTimer);
  adminWs = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws/admin`);
  adminWs.onopen = () => pollAdminState(false);
  adminWs.onmessage = () => location.reload();
  adminWs.onclose = () => { adminTimer = setTimeout(connectAdmin, 1500); };
  adminWs.onerror = () => adminWs.close();
}

connectAdmin();
pollAdminState(false);
setInterval(() => pollAdminState(false), 2000);
setInterval(() => {
  if (adminWs && adminWs.readyState === WebSocket.OPEN) adminWs.send("ping");
}, 25000);