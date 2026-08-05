/**
 * Stockage du jeton JWT côté client.
 *
 * localStorage suffit pour une application personnelle auto-hébergée. Le jour
 * où REVISIO devient multi-utilisateurs public, on migrera vers un cookie
 * httpOnly posé par le backend (insensible au XSS) — le reste du code ne
 * verra pas la différence puisqu'il passe par ces trois fonctions.
 */

const TOKEN_KEY = "revisio_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}
