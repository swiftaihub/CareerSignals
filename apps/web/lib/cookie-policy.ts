import { getCookiePath } from "./app-path";

export interface CookieWriter {
  set(
    name: string,
    value: string,
    options: {
      expires?: Date;
      httpOnly?: boolean;
      maxAge?: number;
      path?: string;
      sameSite?: "lax" | "strict" | "none";
      secure?: boolean;
    }
  ): unknown;
}

export function secureAppCookieOptions() {
  return {
    httpOnly: true as const,
    secure: process.env.NODE_ENV === "production",
    sameSite: "lax" as const,
    path: getCookiePath()
  };
}

/** Expires an application cookie using the exact path used when it was set. */
export function clearAppCookie(writer: CookieWriter, name: string) {
  const options = {
    ...secureAppCookieOptions(),
    expires: new Date(0),
    maxAge: 0
  };
  writer.set(name, "", options);
}

/**
 * Appends a second Set-Cookie header for a legacy Path=/ copy. Next's cookie
 * map keys by name and would otherwise overwrite the new base-scoped cookie.
 */
export function clearLegacyRootCookie(response: { headers: Headers }, name: string) {
  if (getCookiePath() === "/") return;
  if (!/^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/.test(name)) return;
  const secure = process.env.NODE_ENV === "production" ? "; Secure" : "";
  response.headers.append(
    "Set-Cookie",
    `${name}=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; HttpOnly; SameSite=Lax${secure}`
  );
}
