import { http, HttpResponse } from "msw";

export const handlers = [
  http.get("/api/catalog", () =>
    HttpResponse.json([
      {
        id: 1,
        type: "image",
        local_path: "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
        attribution: "img1",
      },
      {
        id: 2,
        type: "image",
        local_path: "data:image/gif;base64,R0lGODlhAQABAIAAAAUEBA==",
        attribution: "img2",
      },
    ]),
  ),
];
