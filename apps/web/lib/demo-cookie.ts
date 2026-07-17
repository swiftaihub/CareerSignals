/** Current and retired Demo cookie names. Retired names are never authorized. */
export const DEMO_TOKEN_COOKIE = "careersignals-demo-token-v2";
export const LEGACY_DEMO_TOKEN_COOKIE = "careersignals-demo-token";
export const DEMO_TOKEN_COOKIE_NAMES = [
  DEMO_TOKEN_COOKIE,
  LEGACY_DEMO_TOKEN_COOKIE
] as const;
