export function logEvent(event: string, data: Record<string, unknown> = {}): void {
  if (process.env.NEXT_PUBLIC_DEV_LOGGING !== "true") return;
  console.log(JSON.stringify({ event, ...data }));
}
