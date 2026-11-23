const key = "ates.session";

export function token() {
  return sessionStorage.getItem(key);
}

export function setToken(value) {
  if (value) sessionStorage.setItem(key, value);
  else sessionStorage.removeItem(key);
}

export async function request(path, {method = "GET", body, signal} = {}) {
  const session = token();
  const multipart = body instanceof FormData;
  const response = await fetch(path, {
    method, signal,
    headers: {
      ...(body && !multipart ? {"Content-Type": "application/json"} : {}),
      ...(session ? {"Authorization": "Bearer " + session} : {}),
    },
    body: multipart ? body : body ? JSON.stringify(body) : undefined,
  });
  if (response.status === 204) return null;
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401 && path !== "/auth/login") {
      setToken(null);
      window.dispatchEvent(new CustomEvent("ates-expired"));
    }
    const error = new Error(data.detail?.message || "The request could not be completed.");
    error.fields = data.detail?.fields || {};
    throw error;
  }
  return data;
}

export async function downloadFile(path, filename) {
  const response = await fetch(path, {headers: {Authorization: "Bearer " + token()}});
  if (response.status === 401) {
    setToken(null);
    window.dispatchEvent(new CustomEvent("ates-expired"));
  }
  if (!response.ok) throw new Error("The file could not be downloaded.");
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

