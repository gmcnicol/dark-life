"use client";
import { useEffect } from "react";

export default function MswProvider() {
  useEffect(() => {
    if (import.meta.env.DEV) {
      import("./browser").then(({ worker }) => worker.start());
    }
  }, []);
  return null;
}
