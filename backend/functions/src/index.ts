import { logger } from "firebase-functions";
import { onRequest } from "firebase-functions/v2/https";

const allowedOrigins = (process.env.CORS_ORIGINS ?? "")
  .split(",")
  .map((value) => value.trim())
  .filter(Boolean);

function applyCors(req: any, res: any) {
  const origin = (req.get("origin") ?? "").trim();
  const originAllowed =
    !allowedOrigins.length || (origin && allowedOrigins.includes(origin));

  if (!originAllowed) {
    res.status(403).json({ ok: false, error: "Origin is not allowed" });
    return false;
  }

  if (origin) {
    res.set("Access-Control-Allow-Origin", origin);
    res.set("Vary", "Origin");
  }
  res.set("Access-Control-Allow-Headers", "Authorization, Content-Type");
  res.set("Access-Control-Allow-Methods", "POST, OPTIONS");

  if (req.method === "OPTIONS") {
    res.status(204).send("");
    return false;
  }

  return true;
}

function requireBearerToken(req: any, res: any) {
  const expectedToken = (process.env.FUNCTIONS_BEARER_TOKEN ?? "").trim();
  if (!expectedToken) {
    res
      .status(503)
      .json({ ok: false, error: "FUNCTIONS_BEARER_TOKEN is not configured" });
    return false;
  }

  const authorization = (req.get("authorization") ?? "").trim();
  if (authorization !== `Bearer ${expectedToken}`) {
    res.status(401).json({ ok: false, error: "Unauthorized" });
    return false;
  }

  return true;
}

export const ping = onRequest({ cors: false }, async (req, res) => {
  if (!applyCors(req, res) || !requireBearerToken(req, res)) return;
  res.json({ ok: true, time: new Date().toISOString() });
});

function isQuotaError(msg: string) {
  const m = (msg || "").toLowerCase();
  return (
    m.includes("resource_exhausted") || m.includes("quota") || m.includes("429")
  );
}

export const ask = onRequest({ cors: false }, async (req, res) => {
  try {
    if (!applyCors(req, res) || !requireBearerToken(req, res)) return;
    const message = (req.body?.message ?? "").toString().trim();
    if (!message) {
      res.status(400).json({ ok: false, error: "message is required" });
      return;
    }

    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      res.status(500).json({
        ok: false,
        error: "GEMINI_API_KEY is missing in functions/.env.local",
      });
      return;
    }

    const { GoogleGenAI } = await import("@google/genai");
    const ai = new GoogleGenAI({ apiKey });

    // جرّب الأدق أولاً، ثم الأخف
    const models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"];

    let lastErr: any = null;
    for (const model of models) {
      try {
        const resp = await ai.models.generateContent({
          model,
          contents: message,
        });
        res.json({ ok: true, model, answer: resp.text ?? "" });
        return;
      } catch (e: any) {
        lastErr = e;
        const msg = e?.message ?? String(e);
        // إذا كوتا/429 جرّب الموديل اللي بعده
        if (isQuotaError(msg)) continue;
        // أي خطأ ثاني نوقف مباشرة
        throw e;
      }
    }

    // لو كل الموديلات عليها كوتا 0
    const msg = lastErr?.message ?? String(lastErr);
    res.status(429).json({
      ok: false,
      error:
        "كل الموديلات رجّعت Quota/429. هذا يعني Free tier عندك = 0 أو غير مفعّل. الحل: تفعيل Billing أو استخدام نموذج محلي (LM Studio/Ollama).",
      details: msg,
    });
  } catch (err: any) {
    logger.error(err);
    res.status(500).json({ ok: false, error: err?.message ?? String(err) });
  }
});
