import { request } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

import { AUTH_HEADERS, AUTH_STATE, demoPassword } from "./auth";
import { BASE_URL } from "./simulation";

export default async function setup() {
  const api = await request.newContext({ baseURL: BASE_URL });
  try {
    const response = await api.post("/api/v1/auth/login", {
      data: { username: "admin", password: await demoPassword("admin") },
    });
    if (!response.ok())
      throw new Error(
        `Demo sign-in failed (${String(response.status())}); migrate configured credentials.`,
      );
    const result: unknown = await response.json();
    if (
      typeof result !== "object" ||
      result === null ||
      !("csrf_token" in result) ||
      typeof result.csrf_token !== "string"
    ) {
      throw new Error("Demo sign-in returned an invalid session envelope.");
    }
    const state = await api.storageState();
    const sessionCookie = state.cookies.find((item) => item.name === "iphi_session");
    if (!sessionCookie) throw new Error("Demo sign-in did not set a session cookie.");
    await mkdir(dirname(AUTH_STATE), { recursive: true, mode: 0o700 });
    await writeFile(AUTH_STATE, JSON.stringify(state), { mode: 0o600 });
    await writeFile(
      AUTH_HEADERS,
      JSON.stringify({ cookie: `iphi_session=${sessionCookie.value}`, csrf: result.csrf_token }),
      { mode: 0o600 },
    );
  } finally {
    await api.dispose();
  }
}
