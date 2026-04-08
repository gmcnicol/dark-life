declare module "./server/admin-proxy.mjs" {
  import type { IncomingMessage, ServerResponse } from "node:http";

  export function isAdminProxyRequest(url?: string): boolean;
  export function handleAdminProxy(
    req: IncomingMessage,
    res: ServerResponse,
    options: { apiBase: string },
  ): Promise<boolean>;
}
