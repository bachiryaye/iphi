import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";

export const AUTH_STATE = fileURLToPath(
  new URL("../.playwright/admin-state.json", import.meta.url),
);
export const AUTH_HEADERS = fileURLToPath(
  new URL("../.playwright/admin-headers.json", import.meta.url),
);

export async function demoPassword(role: "viewer" | "engineer" | "admin"): Promise<string> {
  const key = `IPHI_DEMO_${role.toUpperCase()}_PASSWORD`;
  const configured = process.env[key];
  if (configured) return configured;
  const content = await readFile(new URL("../../.env", import.meta.url), "utf8");
  const value = new RegExp(`^${key}=(.*)$`, "m").exec(content)?.[1]?.trim();
  if (!value) throw new Error("Demo account missing; run make init-env and migrate.");
  return value.replace(/^["']|["']$/g, "");
}

let headers: Promise<{ cookie: string; csrf: string }> | undefined;
export function savedAuth() {
  headers ??= readFile(AUTH_HEADERS, "utf8").then((raw) => {
    const value: unknown = JSON.parse(raw);
    if (
      typeof value !== "object" ||
      value === null ||
      !("cookie" in value) ||
      !("csrf" in value) ||
      typeof value.cookie !== "string" ||
      typeof value.csrf !== "string"
    ) {
      throw new Error("Invalid local test session state.");
    }
    return { cookie: value.cookie, csrf: value.csrf };
  });
  return headers;
}
