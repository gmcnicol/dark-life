import { useEffect, useMemo, useState } from "react";

export const READER_SIZE_PRESETS = [
  { id: "compact", label: "Compact", fontSize: "1rem", lineHeight: "1.95rem" },
  { id: "comfortable", label: "Comfortable", fontSize: "1.12rem", lineHeight: "2.15rem" },
  { id: "large", label: "Large", fontSize: "1.24rem", lineHeight: "2.35rem" },
  { id: "x-large", label: "X-Large", fontSize: "1.36rem", lineHeight: "2.55rem" },
] as const;

export type ReaderSizeId = (typeof READER_SIZE_PRESETS)[number]["id"];

const DEFAULT_READER_SIZE: ReaderSizeId = "comfortable";
const STORAGE_KEY = "darklife:reader-size";

export function useReaderPreferences(storageKey = STORAGE_KEY) {
  const [size, setSize] = useState<ReaderSizeId>(DEFAULT_READER_SIZE);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const stored = window.localStorage.getItem(storageKey);
    if (stored && READER_SIZE_PRESETS.some((preset) => preset.id === stored)) {
      setSize(stored as ReaderSizeId);
    }
  }, [storageKey]);

  const updateSize = (next: ReaderSizeId) => {
    setSize(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(storageKey, next);
    }
  };

  const preset = useMemo(
    () => READER_SIZE_PRESETS.find((candidate) => candidate.id === size) ?? READER_SIZE_PRESETS[1],
    [size],
  );

  return {
    size,
    setSize: updateSize,
    preset,
  };
}
