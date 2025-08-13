"use client";
import { useEffect } from "react";

export default function MswProvider() {
  useEffect(() => {
    if (process.env.NODE_ENV !== "production") {
      import("./browser").then(({ worker }) => worker.start());
    }
  }, []);
  return null;
}
