export function logEvent(event: string, data: Record<string, unknown> = {}): void {
  if (import.meta.env.VITE_DEV_LOGGING !== "true") return;
  console.log(JSON.stringify({ event, ...data }));
}
