"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { logEvent } from "@/lib/log";

export default function KeyboardShortcuts() {
  const router = useRouter();
  const awaiting = useRef(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "g") {
        awaiting.current = true;
        return;
      }
      if (awaiting.current) {
        if (e.key === "i") {
          router.push("/inbox");
          logEvent("shortcut", { keys: "g i" });
        } else if (e.key === "b") {
          router.push("/board");
          logEvent("shortcut", { keys: "g b" });
        }
        awaiting.current = false;
        return;
      }
      if (e.key === "/") {
        const input = document.getElementById("global-search") as HTMLInputElement | null;
        if (input) {
          e.preventDefault();
          input.focus();
          logEvent("shortcut", { keys: "/" });
        }
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router]);

  return null;
}
