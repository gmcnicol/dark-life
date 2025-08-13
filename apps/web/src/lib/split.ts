export const WORDS_PER_MINUTE = 160;
export const WORDS_PER_SECOND = WORDS_PER_MINUTE / 60;

export function segmentSentences(text: string): string[] {
  return text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

export function estimateDuration(words: number): number {
  return Math.round(words / WORDS_PER_SECOND);
}

export function splitSentences(
  sentences: string[],
  targetSeconds = 60,
): string[][] {
  const wordsPerPart = Math.floor(targetSeconds * WORDS_PER_SECOND);
  const parts: string[][] = [];
  let current: string[] = [];
  let wordCount = 0;
  for (const sentence of sentences) {
    const words = sentence.split(/\s+/).filter(Boolean).length;
    if (current.length && wordCount + words > wordsPerPart) {
      parts.push(current);
      current = [];
      wordCount = 0;
    }
    current.push(sentence);
    wordCount += words;
  }
  if (current.length) {
    parts.push(current);
  }
  return parts;
}
