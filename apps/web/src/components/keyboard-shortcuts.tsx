"use client";

import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { logEvent } from "@/lib/log";

export default function KeyboardShortcuts() {
  const navigate = useNavigate();
  const awaiting = useRef(false);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "g") {
        awaiting.current = true;
        return;
      }
      if (awaiting.current) {
        if (e.key === "i") {
          navigate("/inbox");
          logEvent("shortcut", { keys: "g i" });
        } else if (e.key === "b") {
          navigate("/board");
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
  }, [navigate]);

  return null;
}
