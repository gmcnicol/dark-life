import { describe, expect, it } from "vitest";
import { estimateDuration, segmentSentences, splitSentences } from "./split";

describe("segmentSentences", () => {
  it("splits text by punctuation", () => {
    const text = "Hello world. How are you? I'm fine!";
    expect(segmentSentences(text)).toEqual([
      "Hello world.",
      "How are you?",
      "I'm fine!",
    ]);
  });
});

describe("estimateDuration", () => {
  it("estimates seconds from word count", () => {
    expect(estimateDuration(160)).toBe(60);
    expect(estimateDuration(80)).toBe(30);
  });
});

describe("splitSentences", () => {
  it("splits sentences into parts around target length", () => {
    const sentences = [
      "one two three.",
      "four five six.",
      "seven eight nine ten eleven twelve.",
    ];
    const parts = splitSentences(sentences, 2); // target 2 sec ~ 5 words
    expect(parts.length).toBe(3);
    expect(parts[0].join(" ")).toContain("one");
    expect(parts[2].join(" ")).toContain("seven");
  });
});
