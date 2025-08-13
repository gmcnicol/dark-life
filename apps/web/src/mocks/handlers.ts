import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/catalog", () =>
    HttpResponse.json([
      {
        url: "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
        nsfw: false,
        attribution: "img1",
      },
      {
        url: "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
        nsfw: true,
        attribution: "img2",
      },
    ]),
  ),
];
