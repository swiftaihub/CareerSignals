/** Allows only explicit HTTP(S) links supplied by backend job data. */
export function safeExternalHttpUrl(value: unknown) {
  if (
    typeof value !== "string"
    || !value.trim()
    || /[\\\u0000-\u001f\u007f]/.test(value)
  ) {
    return null;
  }

  try {
    const parsed = new URL(value);
    if (
      (parsed.protocol !== "http:" && parsed.protocol !== "https:")
      || parsed.username
      || parsed.password
    ) {
      return null;
    }
    return parsed.href;
  } catch {
    return null;
  }
}
