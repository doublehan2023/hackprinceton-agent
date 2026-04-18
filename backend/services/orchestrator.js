import { callGemini } from "./gemini.js";
import { callK2 } from "./k2.js";

/**
 * AI Router — routes prompts to the right model based on clause type.
 * K2 handles heavy legal reasoning (IP, indemnification, publication).
 * Gemini handles fast summarization and general clause analysis.
 * 
 * FIX: Added null fallback — if K2 is unavailable, gracefully falls to Gemini.
 */
export async function routeAI(prompt, clauseType = "") {

  const combined = (prompt + " " + clauseType).toLowerCase();

  const isLegalHeavy =
    combined.includes("indemn") ||
    combined.includes("intellectual property") ||
    combined.includes(" ip ") ||
    combined.includes("publication") ||
    combined.includes("patent") ||
    combined.includes("ownership") ||
    combined.includes("liability");

  if (isLegalHeavy) {
    const k2Result = await callK2(prompt);

    // FIX: Graceful fallback if K2 fails or key not configured
    if (k2Result) {
      return { result: k2Result, model: "K2" };
    }

    console.warn("K2 unavailable — falling back to Gemini for legal clause");
  }

  const geminiResult = await callGemini(prompt);
  return { result: geminiResult, model: "Gemini" };
}