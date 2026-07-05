// Same-origin in dev thanks to the Vite proxy (/api -> FastAPI :8000).
export async function fetchRates() {
  const resp = await fetch("/api/fx/");
  if (!resp.ok) throw new Error("fx failed");
  return resp.json();
}

export async function extractTrip(url, persona) {
  const resp = await fetch("/api/extract/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, persona }),
  });
  let data = {};
  try { data = await resp.json(); } catch { /* non-json error */ }
  if (!resp.ok) {
    throw new Error((data && data.detail) || `Request failed (${resp.status})`);
  }
  return data;
}
