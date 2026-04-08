"use client";

import { Fragment, useEffect, useState } from "react";
import { cn } from "@/lib/utils";

const DEFAULT_STORAGE_KEY = "darklife:bionic-reading";

export function BionicText({
  text,
  className,
  storageKey = DEFAULT_STORAGE_KEY,
  showToggle = false,
}: {
  text: string;
  className?: string;
  storageKey?: string;
  showToggle?: boolean;
}) {
  const [enabled, setEnabled] = useState(true);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(storageKey);
    if (stored === "off") {
      setEnabled(false);
      return;
    }
    if (stored === "on") {
      setEnabled(true);
    }
  }, [storageKey]);

  const toggle = () => {
    setEnabled((current) => {
      const next = !current;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(storageKey, next ? "on" : "off");
      }
      return next;
    });
  };

  const preparedText = normalizeTextForReading(text);
  const paragraphs = preparedText.split(/\n{2,}/).filter((paragraph) => paragraph.trim().length > 0);

  return (
    <div className="space-y-3">
      {showToggle ? <BionicReadingToggle enabled={enabled} onToggle={toggle} /> : null}

      <div className={cn("break-words", className)}>
        {(paragraphs.length > 0 ? paragraphs : [preparedText]).map((paragraph, paragraphIndex) => (
          <p key={paragraphIndex} className={paragraphIndex === 0 ? "" : "mt-5"}>
            {enabled ? renderBionicParagraph(paragraph) : paragraph}
          </p>
        ))}
      </div>
    </div>
  );
}

export function BionicReadingToggle({
  enabled,
  onToggle,
}: {
  enabled?: boolean;
  onToggle?: () => void;
}) {
  const [localEnabled, setLocalEnabled] = useState(true);
  const active = enabled ?? localEnabled;

  useEffect(() => {
    if (enabled !== undefined || typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(DEFAULT_STORAGE_KEY);
    if (stored === "off") {
      setLocalEnabled(false);
      return;
    }
    if (stored === "on") {
      setLocalEnabled(true);
    }
  }, [enabled]);

  const handleToggle = () => {
    if (onToggle) {
      onToggle();
      return;
    }
    setLocalEnabled((current) => {
      const next = !current;
      if (typeof window !== "undefined") {
        window.localStorage.setItem(DEFAULT_STORAGE_KEY, next ? "on" : "off");
      }
      return next;
    });
  };

  return (
    <div className="flex items-center justify-between gap-3">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.22em] text-[var(--muted)]">
        Reading mode
      </p>
      <button
        type="button"
        onClick={handleToggle}
        className={cn(
          "rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] transition",
          active
            ? "border-cyan-400/30 bg-cyan-400/12 text-cyan-100"
            : "border-white/10 bg-white/5 text-[var(--text-soft)] hover:bg-white/8",
        )}
      >
        {active ? "Bionic on" : "Bionic off"}
      </button>
    </div>
  );
}

function renderBionicParagraph(paragraph: string) {
  return paragraph.split(/(\s+)/).map((token, index) => {
    if (!token.trim()) {
      return <Fragment key={index}>{token}</Fragment>;
    }

    const match = token.match(/^([^A-Za-z0-9]*)([A-Za-z0-9][A-Za-z0-9'’-]*)([^A-Za-z0-9]*)$/);
    if (!match) {
      return <Fragment key={index}>{token}</Fragment>;
    }

    const [, leading, word, trailing] = match;
    if (!word) {
      return <Fragment key={index}>{token}</Fragment>;
    }
    const pivot = Math.min(word.length, Math.max(1, Math.ceil(word.length * 0.42)));

    return (
      <Fragment key={index}>
        {leading}
        <strong className="font-semibold text-white/92">{word.slice(0, pivot)}</strong>
        <span className="text-white/76">{word.slice(pivot)}</span>
        {trailing}
      </Fragment>
    );
  });
}

function normalizeTextForReading(text: string) {
  return text
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, "$1")
    .replace(/https?:\/\/\S+/g, (url) => {
      try {
        const parsed = new URL(url);
        return ` ${parsed.hostname.replace(/^www\./, "")} `;
      } catch {
        return " link ";
      }
    })
    .replace(/[ \t]+\n/g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}
