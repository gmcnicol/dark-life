import { NextRequest } from "next/server";
import { GET as proxyGet } from "../[...path]/route";

export async function GET(req: NextRequest) {
  return proxyGet(req, {
    params: Promise.resolve({ path: ["assets", "library"] }),
  });
}
