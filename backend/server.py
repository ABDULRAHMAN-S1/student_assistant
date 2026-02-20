import json
import re
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from dotenv import load_dotenv

# --- تحميل .env ---
load_dotenv()

# --- إعدادات ---
BASE_DIR = Path(__file__).parent
KB_FILE = BASE_DIR / "kb.json"

USE_GEMINI = os.getenv("USE_GEMINI", "1") == "1"
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
API_KEY = os.getenv("GEMINI_API_KEY")

# --- تحميل قاعدة المعرفة ---
KB = json.loads(KB_FILE.read_text(encoding="utf-8")) if KB_FILE.exists() else []

# --- كلمات عامة/استفهامية (لا نستخدمها في التطابق) ---
STOP_WORDS_AR = {
    "كم","كيف","ليش","لماذا","وش","ايش","متى","وين","من","ما","هل","ماذا",
    "انا","أبي","ابي","ابغى","بغيت","لو","او","و","ثم",
    "في","على","عن","إلى","الى","مع","بدون","داخل","خارج",
    "هذا","هذه","ذلك","تلك","هذي","ذي","هاذا",
    "please","plz"
}

def norm_ar(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[ًٌٍَُِّْـ]", "", text)                 # حركات
    text = re.sub(r"[^\w\s\u0600-\u06FF]", " ", text)       # رموز
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize(text: str):
    words = norm_ar(text).split()
    # حذف كلمات عامة + كلمات قصيرة جدًا
    words = [w for w in words if (w not in STOP_WORDS_AR and len(w) >= 3)]
    return set(words)

def retrieve(question: str, top_k: int = 3):
    q_words = tokenize(question)
    if not q_words:
        return []

    scored = []
    for it in KB:
        t_words = tokenize(it.get("text", ""))
        score = len(q_words & t_words)
        if score > 0:
            scored.append((score, it))

    scored.sort(key=lambda x: x[0], reverse=True)

    # إذا أفضل نتيجة ضعيفة جدًا (تطابق كلمة واحدة فقط) نعتبره غير كافي
    if scored and scored[0][0] <= 1:
        return []

    return [x[1] for x in scored[:top_k]]

# --- Gemini (اختياري) ---
gemini_client = None
if USE_GEMINI and API_KEY:
    try:
        from google import genai
        gemini_client = genai.Client(api_key=API_KEY)
    except Exception:
        gemini_client = None

def is_quota_error(msg: str) -> bool:
    msg_l = (msg or "").lower()
    return ("resource_exhausted" in msg_l) or ("quota" in msg_l) or ("429" in msg_l)

def format_kb_fallback(hits):
    # رد مباشر من KB (بدون Gemini)
    return "حسب معلوماتي الخاصة:\n\n" + "\n\n".join([f"• {h.get('text','')}" for h in hits])

def ask_gemini_nice(question: str, hits):
    """
    Gemini يصيغ جواب جميل لكن "فقط" باستخدام المعلومات الخاصة.
    """
    context = "\n".join([f"- ({h.get('id','')}) {h.get('text','')}" for h in hits])

    prompt = f"""
أنت مساعد يجيب اعتماداً على "المعلومات الخاصة" فقط.
ممنوع استخدام معرفة عامة أو تخمين.
إذا المعلومات الخاصة لا تحتوي جواباً مباشراً، قل حرفياً:
"ما عندي معلومة كافية من معلوماتي الخاصة."

اكتب جواباً عربيًا واضحًا ومختصرًا (5-10 أسطر)، واذا فيه خطوات خلها نقاط مرتبة.

[المعلومات الخاصة]
{context}
[/المعلومات الخاصة]

سؤال المستخدم: {question}
""".strip()

    resp = gemini_client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
    return (resp.text or "").strip()

# --- FastAPI ---
app = FastAPI()

# ✅ CORS مضبوط للويب (Flutter Web على localhost:49190)
# تقدر تغيّر/تضيف Origins من .env عبر:
# ALLOW_ORIGINS=http://localhost:49190,http://127.0.0.1:49190
default_origins = [
    "http://localhost:49190",
    "http://127.0.0.1:49190",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

env_origins = os.getenv("ALLOW_ORIGINS", "").strip()
allow_origins = default_origins
if env_origins:
    allow_origins = [x.strip() for x in env_origins.split(",") if x.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,   # ✅ الأفضل بدل "*"
    allow_credentials=False,       # ✅ لا نخليها True مع origins كثيرة
    allow_methods=["*"],
    allow_headers=["*"],
    max_age=86400,                 # ✅ يقلل preflight المتكرر
)

class ChatReq(BaseModel):
    question: str

@app.get("/")
def root():
    return {
        "status": "ok",
        "kb_items": len(KB),
        "use_gemini": bool(gemini_client),
        "allowed_origins": allow_origins,
        "try": ["/docs", "POST /chat"]
    }

@app.post("/chat")
def chat(req: ChatReq):
    hits = retrieve(req.question, top_k=3)

    if not hits:
        return {"reply": "ما عندي معلومة كافية من معلوماتي الخاصة."}

    # إذا Gemini شغال: نخليه يصيغ الرد بشكل جميل
    if gemini_client:
        try:
            nice = ask_gemini_nice(req.question, hits)
            if not nice:
                # احتياط
                return {"reply": format_kb_fallback(hits)}
            return {"reply": nice}
        except Exception as e:
            msg = str(e)
            # إذا كوتا/429: ارجع للـ KB مباشرة بدون ما أطيح
            if is_quota_error(msg):
                return {"reply": format_kb_fallback(hits)}
            return {"reply": format_kb_fallback(hits), "error": msg}

    # إذا Gemini مو شغال: رد KB فقط
    return {"reply": format_kb_fallback(hits)}
