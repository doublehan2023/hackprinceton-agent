/**
 * K2 API Integration
 * Used for heavy legal reasoning tasks (indemnification, IP, publication rights)
 * K2 is routed via orchestrator.js for clauses requiring deeper legal analysis
 * 
 * BUG FIX: This file was completely empty. callK2 was imported in orchestrator.js
 * but never defined, causing a crash on any legal-heavy query.
 */

export async function callK2(prompt) {
  const apiKey = process.env.K2_API_KEY;

  if (!apiKey) {
    console.warn("⚠️ K2_API_KEY not set — falling back to Gemini");
    return null;
  }

  try {
    const res = await fetch("https://api.k2.ai/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        model: "k2-legal",
        messages: [
          {
            role: "system",
            content: `You are a senior clinical trial legal expert specializing in ACTA compliance. 
            Analyze contracts with precision and flag deviations from standard ACTA frameworks.
            Focus on: Indemnification, IP Ownership, Publication Rights, Confidentiality, Payment Terms.`
          },
          {
            role: "user",
            content: prompt
          }
        ],
        temperature: 0.1,
        max_tokens: 2000
      })
    });

    if (!res.ok) {
      const err = await res.text();
      console.error("K2 API error:", err);
      return null;
    }

    const data = await res.json();
    return data?.choices?.[0]?.message?.content || null;

  } catch (err) {
    console.error("K2 call failed:", err);
    return null;
  }
}