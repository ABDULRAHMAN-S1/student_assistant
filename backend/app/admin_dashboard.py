from __future__ import annotations

import json
from html import escape

from app.auth_service import AuthenticatedUser


def _json_script_data(payload: object) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def render_admin_login(*, error_message: str | None = None) -> str:
    error_markup = (
        f'<div class="error-box">{escape(error_message)}</div>'
        if error_message
        else ""
    )

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>دخول لوحة المسؤول</title>
    <style>
      :root {{
        --bg-a: #0f4c75;
        --bg-b: #14b8a6;
        --panel: rgba(255, 255, 255, 0.96);
        --ink: #163247;
        --muted: #5b7688;
        --danger: #c0392b;
        --border: rgba(18, 75, 108, 0.16);
      }}
      * {{
        box-sizing: border-box;
      }}
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 20px;
        font-family: "Segoe UI", Tahoma, sans-serif;
        background:
          radial-gradient(circle at top left, rgba(255,255,255,0.18), transparent 28%),
          linear-gradient(145deg, var(--bg-a), var(--bg-b));
      }}
      .panel {{
        width: min(100%, 460px);
        background: var(--panel);
        border: 1px solid rgba(255,255,255,0.32);
        border-radius: 28px;
        padding: 28px;
        box-shadow: 0 24px 60px rgba(7, 32, 47, 0.28);
      }}
      h1 {{
        margin: 0 0 8px;
        color: var(--ink);
        font-size: 34px;
      }}
      p {{
        margin: 0 0 22px;
        color: var(--muted);
        line-height: 1.8;
      }}
      label {{
        display: block;
        margin-bottom: 8px;
        font-weight: 600;
        color: var(--ink);
      }}
      input {{
        width: 100%;
        padding: 14px 16px;
        border-radius: 14px;
        border: 1px solid var(--border);
        font-size: 15px;
        margin-bottom: 16px;
      }}
      button {{
        width: 100%;
        border: 0;
        border-radius: 16px;
        padding: 14px 18px;
        color: white;
        background: linear-gradient(135deg, #14668f, #1aa3a0);
        font-size: 16px;
        font-weight: 700;
        cursor: pointer;
      }}
      .error-box {{
        margin-bottom: 16px;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(192, 57, 43, 0.08);
        color: var(--danger);
        border: 1px solid rgba(192, 57, 43, 0.18);
      }}
      .hint {{
        margin-top: 14px;
        font-size: 13px;
        color: var(--muted);
      }}
    </style>
  </head>
  <body>
    <main class="panel">
      <h1>لوحة المسؤول</h1>
      <p>سجل الدخول بحساب إداري للوصول إلى أدوات إدارة المستخدمين والأدوار وسجل النشاطات.</p>
      {error_markup}
      <form id="login-form">
        <label for="email">البريد الإلكتروني</label>
        <input id="email" name="email" type="email" required autocomplete="username" />

        <label for="password">كلمة المرور</label>
        <input id="password" name="password" type="password" required autocomplete="current-password" />

        <button type="submit">دخول لوحة المسؤول</button>
      </form>
      <div class="hint">يتم حفظ جلسة الدخول داخل Cookie آمنة على هذا الجهاز.</div>
    </main>
    <script>
      const form = document.getElementById("login-form");
      const errorBox = document.querySelector(".error-box");

      form.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value;

        try {{
          const response = await fetch("/admin/dashboard/login", {{
            method: "POST",
            headers: {{ "Content-Type": "application/json" }},
            body: JSON.stringify({{ email, password }}),
            credentials: "same-origin",
          }});

          const payload = await response.json().catch(() => ({{}}));
          if (!response.ok) {{
            const message = payload.message || "تعذر تسجيل الدخول.";
            if (errorBox) {{
              errorBox.textContent = message;
            }} else {{
              const box = document.createElement("div");
              box.className = "error-box";
              box.textContent = message;
              form.parentNode.insertBefore(box, form);
            }}
            return;
          }}

          window.location.href = payload.redirect_to || "/admin/dashboard";
        }} catch (_) {{
          if (errorBox) {{
            errorBox.textContent = "تعذر الاتصال بالخادم.";
          }}
        }}
      }});
    </script>
  </body>
</html>
"""


def render_admin_dashboard(
    *,
    summary: dict[str, object],
    current_user: AuthenticatedUser,
    token: str,
) -> str:
    summary_cards = [
        ("إجمالي المستخدمين", int(summary.get("total_users", 0))),
        ("المستخدمون النشطون", int(summary.get("active_users", 0))),
        ("المشرفون", int(summary.get("admin_users", 0))),
        ("الطلاب", int(summary.get("student_users", 0))),
        ("الأدوار", int(summary.get("roles", 0))),
        ("سجلات النشاط", int(summary.get("activity_logs", 0))),
        ("الإشعارات", int(summary.get("notifications", 0))),
        ("غير المقروءة", int(summary.get("unread_notifications", 0))),
    ]

    card_markup = "".join(
        f"""
        <article class="metric-card">
          <div class="metric-label">{escape(label)}</div>
          <div class="metric-value">{value}</div>
        </article>
        """
        for label, value in summary_cards
    )

    current_user_payload = {
        "id": current_user.user_id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "permissions": list(current_user.permissions),
    }
    page_payload = {
        "summary": summary,
        "current_user": current_user_payload,
    }

    admin_name = escape(current_user.full_name)
    admin_email = escape(current_user.email)
    token_preview = escape(f"{token[:16]}..." if len(token) > 16 else token)
    permissions_markup = "".join(
        f'<span class="chip">{escape(permission)}</span>'
        for permission in sorted(current_user.permissions)
    )
    hero_status_markup = "".join(
        (
            f'<article class="hero-status-card">'
            f'<strong>{escape(title)}</strong>'
            f'<span>{escape(value)}</span>'
            f"</article>"
        )
        for title, value in [
            ("المستخدمون", f"{int(summary.get('total_users', 0))} حساب تحت المتابعة"),
            ("النشاط", f"{int(summary.get('activity_logs', 0))} عملية مسجلة"),
            ("الأدوار", f"{int(summary.get('roles', 0))} دور وصلاحية"),
            ("مسار الإدارة", "/admin/* محمي بجلسة إدارية"),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>لوحة المسؤول</title>
    <style>
      :root {{
        --bg: #f2f8fb;
        --panel: #ffffff;
        --panel-soft: #f7fbfd;
        --ink: #163247;
        --muted: #5f7c91;
        --line: rgba(18, 75, 108, 0.12);
        --hero-a: #0f5f87;
        --hero-b: #12a79d;
        --accent: #0f7ea0;
        --accent-soft: rgba(15, 126, 160, 0.1);
        --danger: #c0392b;
        --danger-soft: rgba(192, 57, 43, 0.08);
        --warning: #c17a00;
        --warning-soft: rgba(193, 122, 0, 0.1);
        --violet: #6c4ce0;
        --violet-soft: rgba(108, 76, 224, 0.1);
        --success: #198754;
        --success-soft: rgba(25, 135, 84, 0.1);
        --shadow: 0 22px 52px rgba(9, 38, 56, 0.12);
      }}

      * {{
        box-sizing: border-box;
      }}

      body {{
        margin: 0;
        font-family: "Segoe UI", Tahoma, sans-serif;
        background:
          radial-gradient(circle at top right, rgba(18, 167, 157, 0.14), transparent 24%),
          linear-gradient(180deg, #edf7fb 0%, #f9fcfe 100%);
        color: var(--ink);
      }}

      button,
      input,
      select,
      textarea {{
        font: inherit;
      }}

      .page {{
        max-width: 1360px;
        margin: 0 auto;
        padding: 28px 20px 60px;
      }}

      .hero {{
        background: linear-gradient(135deg, var(--hero-a), var(--hero-b));
        color: #fff;
        border-radius: 30px;
        padding: 28px;
        box-shadow: var(--shadow);
        position: relative;
        overflow: hidden;
      }}

      .hero::after {{
        content: "";
        position: absolute;
        width: 420px;
        height: 420px;
        border-radius: 999px;
        left: -120px;
        bottom: -220px;
        background: rgba(255, 255, 255, 0.08);
      }}

      .hero-top {{
        display: flex;
        justify-content: space-between;
        gap: 20px;
        flex-wrap: wrap;
        position: relative;
        z-index: 1;
      }}

      .hero h1 {{
        margin: 0 0 10px;
        font-size: clamp(30px, 4vw, 48px);
        line-height: 1.05;
      }}

      .hero p {{
        margin: 0;
        max-width: 760px;
        line-height: 1.9;
        color: rgba(255, 255, 255, 0.92);
      }}

      .hero-badge {{
        min-width: 280px;
        max-width: 360px;
        background: rgba(10, 48, 71, 0.28);
        border: 1px solid rgba(255, 255, 255, 0.18);
        border-radius: 20px;
        padding: 18px;
        backdrop-filter: blur(8px);
      }}

      .hero-badge strong {{
        display: block;
        margin-bottom: 8px;
        font-size: 15px;
      }}

      .hero-badge span {{
        display: block;
        line-height: 1.7;
        color: rgba(255, 255, 255, 0.9);
        font-size: 14px;
      }}

      .hero-links {{
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 24px;
        position: relative;
        z-index: 1;
      }}

      .hero-links a,
      .hero-links button {{
        color: #fff;
        text-decoration: none;
        padding: 10px 16px;
        border-radius: 999px;
        background: rgba(255, 255, 255, 0.16);
        border: 1px solid rgba(255, 255, 255, 0.18);
        cursor: pointer;
      }}

      .hero-status-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 18px;
        position: relative;
        z-index: 1;
      }}

      .hero-status-card {{
        background: rgba(6, 31, 47, 0.2);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 18px;
        padding: 16px;
        backdrop-filter: blur(8px);
      }}

      .hero-status-card strong {{
        display: block;
        font-size: 13px;
        margin-bottom: 8px;
        color: rgba(255, 255, 255, 0.8);
      }}

      .hero-status-card span {{
        display: block;
        font-size: 16px;
        font-weight: 700;
        line-height: 1.7;
      }}

      .flash {{
        margin-top: 18px;
        padding: 14px 16px;
        border-radius: 18px;
        display: none;
        position: relative;
        z-index: 1;
      }}

      .flash.show {{
        display: block;
      }}

      .flash.success {{
        background: rgba(255, 255, 255, 0.18);
        border: 1px solid rgba(255, 255, 255, 0.24);
      }}

      .flash.error {{
        background: rgba(128, 22, 22, 0.28);
        border: 1px solid rgba(255, 255, 255, 0.14);
      }}

      .grid {{
        display: grid;
        gap: 22px;
        margin-top: 24px;
      }}

      .section {{
        background: var(--panel);
        border-radius: 24px;
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
        padding: 24px;
      }}

      .section-head {{
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 16px;
        flex-wrap: wrap;
        margin-bottom: 18px;
      }}

      .section-head h2 {{
        margin: 0 0 6px;
        font-size: 28px;
      }}

      .section-head p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.8;
      }}

      .eyebrow {{
        margin: 0 0 6px;
        color: #7d98aa;
        font-size: 11px;
        letter-spacing: 0.16em;
      }}

      .metrics-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
        gap: 14px;
      }}

      .metric-card {{
        background: linear-gradient(180deg, #ffffff 0%, var(--panel-soft) 100%);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
        min-height: 120px;
      }}

      .metric-label {{
        color: var(--muted);
        font-size: 14px;
      }}

      .metric-value {{
        margin-top: 18px;
        font-size: 34px;
        font-weight: 800;
      }}

      .meta-grid,
      .split-grid,
      .users-layout {{
        display: grid;
        gap: 16px;
      }}

      .meta-grid {{
        grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      }}

      .split-grid {{
        grid-template-columns: minmax(300px, 420px) minmax(0, 1fr);
      }}

      .users-layout {{
        grid-template-columns: minmax(320px, 380px) minmax(0, 1fr);
      }}

      .card,
      .subpanel {{
        background: #fbfdff;
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px;
      }}

      .card h3,
      .subpanel h3 {{
        margin: 0 0 12px;
        font-size: 18px;
      }}

      .subpanel p,
      .card p {{
        margin: 0 0 14px;
        color: var(--muted);
      }}

      .detail-list {{
        display: grid;
        grid-template-columns: 120px 1fr;
        gap: 10px 12px;
        margin: 0;
      }}

      .detail-list dt {{
        color: var(--muted);
      }}

      .detail-list dd {{
        margin: 0;
        font-weight: 600;
        overflow-wrap: anywhere;
      }}

      .chips {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }}

      .chip {{
        display: inline-flex;
        align-items: center;
        padding: 7px 12px;
        border-radius: 999px;
        background: var(--accent-soft);
        color: var(--accent);
        font-size: 13px;
        font-weight: 600;
      }}

      .notice {{
        display: none;
        padding: 14px 16px;
        border-radius: 16px;
        margin-bottom: 14px;
        line-height: 1.7;
      }}

      .notice.show {{
        display: block;
      }}

      .notice.info {{
        background: var(--accent-soft);
        color: var(--accent);
      }}

      .notice.error {{
        background: var(--danger-soft);
        color: var(--danger);
      }}

      .form-grid {{
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
      }}

      .field {{
        display: grid;
        gap: 8px;
      }}

      .field.full {{
        grid-column: 1 / -1;
      }}

      .field label {{
        font-size: 14px;
        font-weight: 700;
      }}

      .field input,
      .field select,
      .field textarea {{
        width: 100%;
        padding: 12px 14px;
        border-radius: 14px;
        border: 1px solid var(--line);
        background: #fff;
      }}

      .field textarea {{
        min-height: 100px;
        resize: vertical;
      }}

      .checkbox {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        font-weight: 600;
      }}

      .checkbox input {{
        width: auto;
        margin: 0;
      }}

      .actions {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}

      .button {{
        border: 0;
        border-radius: 14px;
        padding: 11px 16px;
        cursor: pointer;
        font-weight: 700;
      }}

      .button.primary {{
        background: linear-gradient(135deg, #12668e, #18a6a3);
        color: #fff;
      }}

      .button.secondary {{
        background: #eef7fb;
        color: var(--ink);
        border: 1px solid var(--line);
      }}

      .button.ghost {{
        background: transparent;
        color: var(--accent);
        border: 1px dashed rgba(15, 126, 160, 0.25);
      }}

      .button:disabled,
      .muted-action:disabled {{
        opacity: 0.55;
        cursor: not-allowed;
      }}

      .table-wrap {{
        overflow: auto;
        border: 1px solid var(--line);
        border-radius: 18px;
      }}

      table {{
        width: 100%;
        border-collapse: collapse;
        min-width: 980px;
        background: #fff;
      }}

      th,
      td {{
        padding: 14px 12px;
        border-bottom: 1px solid var(--line);
        text-align: right;
        vertical-align: top;
      }}

      th {{
        background: #f6fbfd;
        color: var(--muted);
        font-size: 13px;
      }}

      td small {{
        display: block;
        margin-top: 6px;
        color: var(--muted);
        line-height: 1.7;
      }}

      .pill {{
        display: inline-flex;
        align-items: center;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 700;
      }}

      .pill.success {{
        background: var(--success-soft);
        color: var(--success);
      }}

      .pill.danger {{
        background: var(--danger-soft);
        color: var(--danger);
      }}

      .inline-inputs {{
        display: grid;
        gap: 8px;
      }}

      .inline-inputs input,
      .inline-inputs select {{
        min-width: 180px;
      }}

      .role-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 14px;
      }}

      .role-card {{
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 16px;
        background: linear-gradient(180deg, #ffffff 0%, #f8fcff 100%);
      }}

      .role-card h4 {{
        margin: 0 0 8px;
        font-size: 18px;
      }}

      .role-card p {{
        margin: 0 0 12px;
        color: var(--muted);
        line-height: 1.7;
      }}

      .permission-list {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }}

      .permission-box {{
        display: grid;
        gap: 8px;
        max-height: 320px;
        overflow: auto;
        padding: 6px 2px 6px 0;
      }}

      .permission-item {{
        display: grid;
        grid-template-columns: 22px 1fr;
        gap: 10px;
        align-items: start;
        padding: 10px 12px;
        border-radius: 14px;
        background: #fff;
        border: 1px solid var(--line);
      }}

      .permission-item strong {{
        display: block;
        margin-bottom: 4px;
      }}

      .permission-item span {{
        color: var(--muted);
        font-size: 13px;
        line-height: 1.7;
      }}

      .log-list {{
        display: grid;
        gap: 12px;
      }}

      .log-card {{
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 18px 20px 18px 18px;
        background: linear-gradient(180deg, #ffffff 0%, #fbfdff 100%);
        position: relative;
        overflow: hidden;
      }}

      .log-card::before {{
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 4px;
        background: #c9dbe6;
      }}

      .log-head {{
        display: flex;
        justify-content: space-between;
        gap: 12px;
        flex-wrap: wrap;
        margin-bottom: 10px;
        align-items: flex-start;
      }}

      .log-head strong {{
        font-size: 18px;
      }}

      .log-title-stack {{
        display: grid;
        gap: 8px;
      }}

      .log-summary {{
        margin: 0;
        color: var(--muted);
        line-height: 1.8;
      }}

      .log-timebox {{
        min-width: 190px;
        padding: 12px 14px;
        border-radius: 16px;
        background: #f5fbff;
        border: 1px solid var(--line);
        text-align: right;
      }}

      .log-timebox span {{
        display: block;
        font-weight: 700;
        margin-bottom: 6px;
      }}

      .log-timebox small {{
        color: var(--muted);
        overflow-wrap: anywhere;
      }}

      .log-badge-row,
      .log-badges {{
        display: flex;
        gap: 8px;
        flex-wrap: wrap;
      }}

      .log-badges {{
        margin-bottom: 14px;
      }}

      .meta-chip,
      .filter-chip {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 8px 12px;
        border-radius: 999px;
        border: 1px solid var(--line);
        background: #fff;
        color: var(--ink);
        font-size: 13px;
        font-weight: 600;
      }}

      .filter-chip {{
        cursor: pointer;
      }}

      .filter-chip.active {{
        background: var(--accent-soft);
        color: var(--accent);
        border-color: rgba(15, 126, 160, 0.24);
      }}

      .activity-shell {{
        display: grid;
        grid-template-columns: minmax(300px, 360px) minmax(0, 1fr);
        gap: 16px;
      }}

      .activity-main {{
        display: grid;
        gap: 16px;
      }}

      .activity-filter-panel {{
        position: sticky;
        top: 18px;
        align-self: start;
      }}

      .activity-toolbar {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        align-items: center;
      }}

      .activity-toolbar input {{
        min-width: 240px;
      }}

      .quick-filter-row {{
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 12px;
      }}

      .activity-stats {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }}

      .activity-stat-card {{
        background: linear-gradient(180deg, #ffffff 0%, #f7fbfd 100%);
        border: 1px solid var(--line);
        border-radius: 18px;
        padding: 16px;
      }}

      .activity-stat-card strong {{
        display: block;
        margin-bottom: 8px;
        color: var(--muted);
        font-size: 13px;
      }}

      .activity-stat-card span {{
        display: block;
        font-size: 28px;
        font-weight: 800;
      }}

      .activity-timeline {{
        position: relative;
        display: grid;
        gap: 14px;
      }}

      .activity-timeline::before {{
        content: "";
        position: absolute;
        top: 10px;
        bottom: 10px;
        right: 18px;
        width: 2px;
        background: linear-gradient(180deg, rgba(15, 126, 160, 0.2), rgba(18, 167, 157, 0.12));
      }}

      .activity-timeline .log-card {{
        padding-right: 44px;
      }}

      .activity-timeline .log-card::after {{
        content: "";
        position: absolute;
        right: 12px;
        top: 22px;
        width: 14px;
        height: 14px;
        border-radius: 999px;
        background: var(--accent);
        border: 3px solid #fff;
        box-shadow: 0 0 0 4px rgba(15, 126, 160, 0.1);
      }}

      .log-card.tone-auth::before,
      .log-card.tone-auth::after {{
        background: #2563eb;
      }}

      .log-card.tone-users::before,
      .log-card.tone-users::after {{
        background: var(--accent);
      }}

      .log-card.tone-roles::before,
      .log-card.tone-roles::after {{
        background: var(--violet);
      }}

      .log-card.tone-engagement::before,
      .log-card.tone-engagement::after {{
        background: var(--warning);
      }}

      .log-card.tone-general::before,
      .log-card.tone-general::after {{
        background: var(--success);
      }}

      .pill.tone-auth {{
        background: rgba(37, 99, 235, 0.1);
        color: #2563eb;
      }}

      .pill.tone-users {{
        background: var(--accent-soft);
        color: var(--accent);
      }}

      .pill.tone-roles {{
        background: var(--violet-soft);
        color: var(--violet);
      }}

      .pill.tone-engagement {{
        background: var(--warning-soft);
        color: var(--warning);
      }}

      .pill.tone-general {{
        background: var(--success-soft);
        color: var(--success);
      }}

      .log-details {{
        margin: 0 0 14px;
        padding: 0 18px 0 0;
        color: var(--ink);
        line-height: 1.9;
      }}

      .log-json {{
        border-top: 1px solid var(--line);
        padding-top: 12px;
      }}

      .log-json summary {{
        cursor: pointer;
        font-weight: 700;
        color: var(--accent);
      }}

      .log-meta {{
        color: var(--muted);
        font-size: 13px;
        line-height: 1.8;
      }}

      .log-meta code {{
        background: #eef7fb;
        padding: 2px 6px;
        border-radius: 8px;
      }}

      pre {{
        margin: 10px 0 0;
        padding: 12px;
        border-radius: 14px;
        background: #f4f9fc;
        border: 1px solid var(--line);
        overflow: auto;
        white-space: pre-wrap;
        word-break: break-word;
      }}

      .toolbar {{
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
      }}

      .empty-state {{
        padding: 18px;
        border-radius: 18px;
        text-align: center;
        color: var(--muted);
        background: #f8fcff;
        border: 1px dashed var(--line);
      }}

      @media (max-width: 980px) {{
        .users-layout,
        .split-grid,
        .activity-shell {{
          grid-template-columns: 1fr;
        }}

        .activity-filter-panel {{
          position: static;
        }}
      }}

      @media (max-width: 760px) {{
        .page {{
          padding-inline: 14px;
        }}

        .hero,
        .section {{
          padding: 18px;
          border-radius: 22px;
        }}

        .form-grid {{
          grid-template-columns: 1fr;
        }}

        .detail-list {{
          grid-template-columns: 1fr;
        }}

        .hero-status-grid,
        .activity-stats {{
          grid-template-columns: 1fr 1fr;
        }}

        .activity-toolbar input,
        .log-timebox {{
          min-width: 100%;
        }}

        .activity-timeline::before {{
          right: 14px;
        }}

        .activity-timeline .log-card {{
          padding-right: 38px;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <header class="hero">
        <div class="hero-top">
          <div>
            <h1>لوحة المسؤول</h1>
            <p>
              صفحة إدارية كاملة لإدارة المستخدمين والأدوار وسجل النشاطات من مكان واحد.
              يمكنك إضافة مستخدم جديد كأدمن أو كمستخدم عادي، تعديل صلاحياته، وتعقب ما يحدث داخل النظام.
            </p>
          </div>
          <aside class="hero-badge">
            <strong>حالة الوصول</strong>
            <span>تم التحقق من صلاحية الدخول بنجاح.</span>
            <span>المستخدم: {admin_name}</span>
            <span>البريد: {admin_email}</span>
            <span>الرمز الحالي: {token_preview}</span>
          </aside>
        </div>

        <nav class="hero-links">
          <a href="/admin">التحقق الإداري</a>
          <a href="/admin/summary">ملخص JSON</a>
          <a href="/public/health">فحص الصحة</a>
          <a href="/admin/dashboard/logout">تسجيل الخروج</a>
          <button type="button" id="refresh-all">تحديث البيانات</button>
        </nav>

        <div class="hero-status-grid">
          {hero_status_markup}
        </div>

        <div id="flash" class="flash" aria-live="polite"></div>
      </header>

      <div class="grid">
        <section class="section">
          <div class="section-head">
            <div>
              <p class="eyebrow">OVERVIEW</p>
              <h2>ملخص النظام</h2>
              <p>مؤشرات سريعة عن الحسابات والإشعارات وسجل النشاطات.</p>
            </div>
          </div>
          <div class="metrics-grid" id="summary-grid">
            {card_markup}
          </div>
        </section>

        <section class="section">
          <div class="section-head">
            <div>
              <p class="eyebrow">SESSION</p>
              <h2>بيانات الجلسة</h2>
              <p>معلومات المشرف الحالي وصلاحياته الفعالة داخل اللوحة.</p>
            </div>
          </div>
          <div class="meta-grid">
            <article class="card">
              <h3>المستخدم الحالي</h3>
              <dl class="detail-list">
                <dt>الاسم</dt>
                <dd>{admin_name}</dd>
                <dt>البريد</dt>
                <dd>{admin_email}</dd>
                <dt>الدور</dt>
                <dd>{escape(current_user.role)}</dd>
              </dl>
            </article>
            <article class="card">
              <h3>الصلاحيات الحالية</h3>
              <div class="chips">
                {permissions_markup or '<span class="chip">لا توجد صلاحيات فعالة</span>'}
              </div>
            </article>
          </div>
        </section>

        <section class="section">
          <div class="section-head">
            <div>
              <p class="eyebrow">USERS</p>
              <h2>إدارة المستخدمين</h2>
              <p>أضف أدمن جديد أو عدل دور أي مستخدم أو عطله أو خصص له صلاحيات إضافية.</p>
            </div>
          </div>
          <div class="users-layout">
            <aside class="subpanel">
              <h3>إضافة مستخدم أو أدمن</h3>
              <p>يمكنك إنشاء حساب جديد مباشرة من اللوحة وتحديد دوره من البداية.</p>
              <div id="create-user-notice" class="notice"></div>
              <form id="create-user-form">
                <div class="form-grid">
                  <div class="field full">
                    <label for="new-full-name">الاسم الكامل</label>
                    <input id="new-full-name" name="full_name" type="text" required />
                  </div>
                  <div class="field full">
                    <label for="new-email">البريد الإلكتروني</label>
                    <input id="new-email" name="email" type="email" required />
                  </div>
                  <div class="field full">
                    <label for="new-password">كلمة المرور</label>
                    <input id="new-password" name="password" type="password" minlength="10" required />
                  </div>
                  <div class="field">
                    <label for="new-role">الدور</label>
                    <select id="new-role" name="role"></select>
                  </div>
                  <div class="field">
                    <label>&nbsp;</label>
                    <label class="checkbox">
                      <input id="new-is-active" name="is_active" type="checkbox" checked />
                      الحساب فعال
                    </label>
                  </div>
                </div>
                <div class="actions" style="margin-top: 14px;">
                  <button class="button primary" type="submit" id="create-user-button">إضافة المستخدم</button>
                </div>
              </form>
            </aside>

            <div class="subpanel">
              <div class="section-head" style="margin-bottom: 14px;">
                <div>
                  <h3 style="margin-bottom: 6px;">قائمة المستخدمين</h3>
                  <p>ابحث ثم حدث الدور والحالة والصلاحيات الإضافية لكل مستخدم.</p>
                </div>
                <div class="toolbar">
                  <input id="user-search" type="search" placeholder="ابحث بالاسم أو البريد أو الدور" />
                  <button class="button secondary" type="button" id="refresh-users">تحديث المستخدمين</button>
                </div>
              </div>
              <div id="users-notice" class="notice"></div>
              <div class="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>المستخدم</th>
                      <th>الدور والحالة</th>
                      <th>الصلاحيات الفعالة</th>
                      <th>تخصيص الصلاحيات</th>
                      <th>الإجراءات</th>
                    </tr>
                  </thead>
                  <tbody id="users-table-body">
                    <tr><td colspan="5">جاري تحميل المستخدمين...</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </section>

        <section class="section">
          <div class="section-head">
            <div>
              <p class="eyebrow">ROLES</p>
              <h2>الأدوار والصلاحيات</h2>
              <p>راجع الأدوار الحالية أو أنشئ دوراً جديداً بصلاحيات مخصصة.</p>
            </div>
          </div>
          <div class="split-grid">
            <aside class="subpanel">
              <h3>إضافة دور جديد</h3>
              <p>يمكنك إنشاء دور جديد ثم تعيينه للمستخدمين من قسم الإدارة أعلاه.</p>
              <div id="roles-notice" class="notice"></div>
              <form id="create-role-form">
                <div class="form-grid">
                  <div class="field">
                    <label for="role-name">اسم الدور</label>
                    <input id="role-name" name="name" type="text" placeholder="assistant_manager" required />
                  </div>
                  <div class="field">
                    <label for="role-display-name">الاسم المعروض</label>
                    <input id="role-display-name" name="display_name" type="text" placeholder="Assistant Manager" required />
                  </div>
                  <div class="field full">
                    <label for="role-description">الوصف</label>
                    <textarea id="role-description" name="description" placeholder="وصف مختصر لهذا الدور"></textarea>
                  </div>
                  <div class="field full">
                    <label>الصلاحيات</label>
                    <div id="permissions-box" class="permission-box"></div>
                  </div>
                </div>
                <div class="actions" style="margin-top: 14px;">
                  <button class="button primary" type="submit" id="create-role-button">إضافة الدور</button>
                </div>
              </form>
            </aside>

            <div class="subpanel">
              <div class="section-head" style="margin-bottom: 14px;">
                <div>
                  <h3 style="margin-bottom: 6px;">الأدوار الحالية</h3>
                  <p>هذه الأدوار متاحة الآن للتعيين على الحسابات.</p>
                </div>
                <button class="button secondary" type="button" id="refresh-roles">تحديث الأدوار</button>
              </div>
              <div id="roles-list" class="role-grid">
                <div class="empty-state">جاري تحميل الأدوار...</div>
              </div>
            </div>
          </div>
        </section>

        <section class="section">
          <div class="section-head">
            <div>
              <p class="eyebrow">ACTIVITY</p>
              <h2>سجل النشاطات</h2>
              <p>راجع آخر العمليات الإدارية وعمليات الدخول والتعديلات على المستخدمين.</p>
            </div>
          </div>
          <div class="activity-shell">
            <aside class="subpanel activity-filter-panel">
              <h3>فلترة السجل</h3>
              <p>استخدم الفلاتر لتضييق النتائج حسب نوع العملية أو المستخدم المستهدف.</p>
              <form id="activity-filter-form">
                <div class="form-grid">
                  <div class="field">
                    <label for="activity-action">الإجراء</label>
                    <input id="activity-action" name="action" type="text" placeholder="users.updated" />
                  </div>
                  <div class="field">
                    <label for="activity-entity-type">نوع الكيان</label>
                    <input id="activity-entity-type" name="entity_type" type="text" placeholder="user" />
                  </div>
                  <div class="field">
                    <label for="activity-actor-user-id">معرف المنفذ</label>
                    <input id="activity-actor-user-id" name="actor_user_id" type="text" />
                  </div>
                  <div class="field">
                    <label for="activity-target-user-id">معرف المستهدف</label>
                    <input id="activity-target-user-id" name="target_user_id" type="text" />
                  </div>
                  <div class="field">
                    <label for="activity-limit">عدد السجلات</label>
                    <input id="activity-limit" name="limit" type="number" min="1" max="100" value="25" />
                  </div>
                </div>
                <div class="actions" style="margin-top: 14px;">
                  <button class="button primary" type="submit">تطبيق الفلترة</button>
                  <button class="button ghost" type="button" id="reset-activity-filter">إعادة ضبط</button>
                </div>
              </form>

              <div class="field full" style="margin-top: 16px;">
                <label>التصفية السريعة</label>
                <div class="quick-filter-row" id="activity-quick-filters">
                  <button class="filter-chip active" type="button" data-activity-preset="all">الكل</button>
                  <button class="filter-chip" type="button" data-activity-preset="auth">الدخول والجلسات</button>
                  <button class="filter-chip" type="button" data-activity-preset="users">المستخدمون</button>
                  <button class="filter-chip" type="button" data-activity-preset="roles">الأدوار</button>
                  <button class="filter-chip" type="button" data-activity-preset="general">أخرى</button>
                </div>
              </div>
            </aside>

            <div class="activity-main">
              <div id="activity-stats" class="activity-stats">
                <div class="activity-stat-card">
                  <strong>المعروض الآن</strong>
                  <span>0</span>
                </div>
                <div class="activity-stat-card">
                  <strong>المستخدمون</strong>
                  <span>0</span>
                </div>
                <div class="activity-stat-card">
                  <strong>الأدوار</strong>
                  <span>0</span>
                </div>
                <div class="activity-stat-card">
                  <strong>الدخول والجلسات</strong>
                  <span>0</span>
                </div>
              </div>

              <div class="subpanel">
                <div class="section-head" style="margin-bottom: 14px;">
                  <div>
                    <h3 style="margin-bottom: 6px;">آخر النشاطات</h3>
                    <p>يعرض العمليات الإدارية بصياغة أسرع للفهم مع تسلسل زمني أوضح وبيانات قابلة للتتبع.</p>
                  </div>
                  <div class="activity-toolbar">
                    <input id="activity-local-search" type="search" placeholder="ابحث داخل النتائج الحالية" />
                    <button class="button secondary" type="button" id="refresh-activity">تحديث السجل</button>
                  </div>
                </div>
                <div id="activity-notice" class="notice"></div>
                <div id="activity-list" class="log-list activity-timeline">
                  <div class="empty-state">جاري تحميل السجل...</div>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>

    <script id="page-data" type="application/json">{_json_script_data(page_payload)}</script>
    <script>
      const pageData = JSON.parse(document.getElementById("page-data").textContent);
      const currentUser = pageData.current_user || {{}};
      const currentPermissions = new Set(currentUser.permissions || []);
      const state = {{
        summary: pageData.summary || {{}},
        permissions: [],
        roles: [],
        users: [],
        activity: [],
        activityPreset: "all",
        activityFilters: {{
          limit: 25,
          action: "",
          entity_type: "",
          actor_user_id: "",
          target_user_id: "",
        }},
      }};

      const summaryLabels = {{
        total_users: "إجمالي المستخدمين",
        active_users: "المستخدمون النشطون",
        admin_users: "المشرفون",
        student_users: "الطلاب",
        roles: "الأدوار",
        activity_logs: "سجلات النشاط",
        notifications: "الإشعارات",
        unread_notifications: "غير المقروءة",
      }};

      const flash = document.getElementById("flash");
      const summaryGrid = document.getElementById("summary-grid");
      const usersTableBody = document.getElementById("users-table-body");
      const rolesList = document.getElementById("roles-list");
      const permissionsBox = document.getElementById("permissions-box");
      const activityStats = document.getElementById("activity-stats");
      const activityList = document.getElementById("activity-list");
      const newRoleSelect = document.getElementById("new-role");
      const createUserForm = document.getElementById("create-user-form");
      const createRoleForm = document.getElementById("create-role-form");
      const activityFilterForm = document.getElementById("activity-filter-form");
      const activitySearch = document.getElementById("activity-local-search");
      const activityQuickFilters = document.getElementById("activity-quick-filters");
      const userSearch = document.getElementById("user-search");

      function hasPermission(code) {{
        return currentPermissions.has(code);
      }}

      function escapeHtml(value) {{
        return String(value ?? "")
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;");
      }}

      function showFlash(message, kind = "success") {{
        flash.textContent = message;
        flash.className = `flash show ${{kind}}`;
      }}

      function clearFlash() {{
        flash.textContent = "";
        flash.className = "flash";
      }}

      function setNotice(id, message = "", kind = "info") {{
        const node = document.getElementById(id);
        if (!node) {{
          return;
        }}
        if (!message) {{
          node.textContent = "";
          node.className = "notice";
          return;
        }}
        node.textContent = message;
        node.className = `notice show ${{kind}}`;
      }}

      function formatDateTime(value) {{
        if (!value) {{
          return "غير متوفر";
        }}
        try {{
          return new Intl.DateTimeFormat("ar-SA", {{
            dateStyle: "medium",
            timeStyle: "short",
          }}).format(new Date(value));
        }} catch (_) {{
          return String(value);
        }}
      }}

      function formatList(items) {{
        return Array.isArray(items) && items.length ? items.join("، ") : "لا يوجد";
      }}

      function getActivityTone(action) {{
        const normalized = String(action || "").toLowerCase();
        if (normalized.startsWith("auth.")) {{
          return {{ key: "auth", label: "الدخول والجلسات", className: "tone-auth" }};
        }}
        if (normalized.startsWith("users.")) {{
          return {{ key: "users", label: "المستخدمون", className: "tone-users" }};
        }}
        if (normalized.startsWith("roles.")) {{
          return {{ key: "roles", label: "الأدوار", className: "tone-roles" }};
        }}
        if (normalized.startsWith("engagement.")) {{
          return {{ key: "engagement", label: "المحتوى", className: "tone-engagement" }};
        }}
        return {{ key: "general", label: "عام", className: "tone-general" }};
      }}

      function getActivityTitle(action) {{
        const normalized = String(action || "").toLowerCase();
        const labels = {{
          "auth.login": "تسجيل دخول",
          "auth.register": "تسجيل مستخدم جديد",
          "auth.refresh": "تجديد جلسة",
          "users.created": "إنشاء مستخدم",
          "users.updated": "تحديث بيانات مستخدم",
          "users.permissions_updated": "تعديل صلاحيات مستخدم",
          "users.role_updated": "تحديث دور مستخدم",
          "roles.created": "إنشاء دور",
          "roles.updated": "تحديث دور",
        }};
        return labels[normalized] || String(action || "نشاط إداري");
      }}

      function getActivitySummary(item) {{
        const metadata = item.metadata || {{}};
        switch (String(item.action || "").toLowerCase()) {{
          case "auth.login":
            return "تمت مصادقة المستخدم وفتح جلسة وصول جديدة للنظام.";
          case "auth.register":
            return "تم إنشاء حساب جديد وإصدار جلسة أولية له.";
          case "auth.refresh":
            return "تم تدوير رمز التحديث وإصدار جلسة جديدة للمستخدم.";
          case "users.created":
            return `تم إنشاء الحساب بالبريد ${{metadata.email || "غير محدد"}} وربطه بالدور ${{metadata.role || "غير محدد"}}.`;
          case "users.updated":
            return "تم تحديث حالة الحساب أو دوره من لوحة الإدارة.";
          case "users.permissions_updated":
            return "تم تعديل الصلاحيات الممنوحة أو المسحوبة لهذا المستخدم.";
          case "roles.created":
            return "تم إنشاء دور جديد وإتاحته للتعيين على الحسابات.";
          case "roles.updated":
            return "تم تحديث صلاحيات الدور أو بياناته الوصفية.";
          default:
            return "حدث إداري مسجل مع تفاصيل قابلة للتتبع داخل النظام.";
        }}
      }}

      function getActivityHighlights(item) {{
        const metadata = item.metadata || {{}};
        const highlights = [];

        if (metadata.email) {{
          highlights.push(`البريد المرتبط: ${{metadata.email}}`);
        }}
        if (metadata.previous_role || metadata.new_role) {{
          highlights.push(`الدور: ${{metadata.previous_role || "غير محدد"}} ← ${{metadata.new_role || "غير محدد"}}`);
        }}
        if (Object.prototype.hasOwnProperty.call(metadata, "previous_is_active") || Object.prototype.hasOwnProperty.call(metadata, "new_is_active")) {{
          highlights.push(`حالة التفعيل: ${{metadata.previous_is_active ? "فعال" : "معطل"}} ← ${{metadata.new_is_active ? "فعال" : "معطل"}}`);
        }}
        if (Array.isArray(metadata.permissions) && metadata.permissions.length) {{
          highlights.push(`صلاحيات الدور: ${{formatList(metadata.permissions)}}`);
        }}
        if (Array.isArray(metadata.granted_permissions) && metadata.granted_permissions.length) {{
          highlights.push(`صلاحيات ممنوحة: ${{formatList(metadata.granted_permissions)}}`);
        }}
        if (Array.isArray(metadata.revoked_permissions) && metadata.revoked_permissions.length) {{
          highlights.push(`صلاحيات مسحوبة: ${{formatList(metadata.revoked_permissions)}}`);
        }}

        return highlights.slice(0, 4);
      }}

      function renderActivityStats(items) {{
        const counts = {{
          all: items.length,
          users: 0,
          roles: 0,
          auth: 0,
          general: 0,
        }};

        items.forEach((item) => {{
          const tone = getActivityTone(item.action);
          if (tone.key in counts) {{
            counts[tone.key] += 1;
          }} else {{
            counts.general += 1;
          }}
        }});

        activityStats.innerHTML = [
          ["المعروض الآن", counts.all],
          ["المستخدمون", counts.users],
          ["الأدوار", counts.roles],
          ["الدخول والجلسات", counts.auth],
        ]
          .map(([label, value]) => `
            <article class="activity-stat-card">
              <strong>${{escapeHtml(label)}}</strong>
              <span>${{Number(value || 0)}}</span>
            </article>
          `)
          .join("");
      }}

      function activityMatchesQuickPreset(item) {{
        if (state.activityPreset === "all") {{
          return true;
        }}
        return getActivityTone(item.action).key === state.activityPreset;
      }}

      function activityMatchesSearch(item, query) {{
        if (!query) {{
          return true;
        }}
        const haystack = JSON.stringify([
          item.action,
          item.entity_type,
          item.entity_id,
          item.actor_user_id,
          item.target_user_id,
          item.metadata || {{}},
        ]).toLowerCase();
        return haystack.includes(query);
      }}

      function syncActivityPresetButtons() {{
        Array.from(activityQuickFilters.querySelectorAll("[data-activity-preset]")).forEach((button) => {{
          const isActive = button.getAttribute("data-activity-preset") === state.activityPreset;
          button.classList.toggle("active", isActive);
        }});
      }}

      async function api(path, options = {{}}) {{
        const response = await fetch(path, {{
          credentials: "same-origin",
          headers: {{
            "Content-Type": "application/json",
            ...(options.headers || {{}}),
          }},
          ...options,
        }});

        const payload = await response.json().catch(() => ({{}}));
        if (!response.ok) {{
          const message =
            payload?.error?.message ||
            payload?.message ||
            "تعذر تنفيذ الطلب.";
          if (response.status === 401) {{
            showFlash("انتهت الجلسة. سيتم تحويلك إلى صفحة الدخول.", "error");
            window.setTimeout(() => {{
              window.location.href = "/admin/dashboard/login";
            }}, 1200);
          }}
          throw new Error(message);
        }}
        return payload;
      }}

      function renderSummary() {{
        const keys = [
          "total_users",
          "active_users",
          "admin_users",
          "student_users",
          "roles",
          "activity_logs",
          "notifications",
          "unread_notifications",
        ];
        summaryGrid.innerHTML = keys
          .map((key) => `
            <article class="metric-card">
              <div class="metric-label">${{escapeHtml(summaryLabels[key] || key)}}</div>
              <div class="metric-value">${{Number(state.summary[key] || 0)}}</div>
            </article>
          `)
          .join("");
      }}

      async function loadSummary() {{
        if (!hasPermission("admin.summary.read")) {{
          return;
        }}
        const payload = await api("/admin/summary", {{ method: "GET" }});
        state.summary = payload.summary || {{}};
        renderSummary();
      }}

      function getRoleChoices(extraValue = "") {{
        const names = new Set(["student", "admin"]);
        state.roles.forEach((item) => names.add(item.name));
        if (extraValue) {{
          names.add(extraValue);
        }}
        return Array.from(names);
      }}

      function renderRoleSelectOptions(selected = "student") {{
        return getRoleChoices(selected)
          .map((name) => `
            <option value="${{escapeHtml(name)}}" ${{name === selected ? "selected" : ""}}>
              ${{escapeHtml(name)}}
            </option>
          `)
          .join("");
      }}

      function renderRoleSelects() {{
        newRoleSelect.innerHTML = renderRoleSelectOptions("student");
      }}

      function renderPermissionsCatalog() {{
        if (!state.permissions.length) {{
          permissionsBox.innerHTML = '<div class="empty-state">لا توجد صلاحيات متاحة للعرض.</div>';
          return;
        }}
        permissionsBox.innerHTML = state.permissions
          .map((permission) => `
            <label class="permission-item">
              <input type="checkbox" name="permissions" value="${{escapeHtml(permission.code)}}" />
              <span>
                <strong>${{escapeHtml(permission.label)}}</strong>
                <span>${{escapeHtml(permission.description)}}<br /><code>${{escapeHtml(permission.code)}}</code></span>
              </span>
            </label>
          `)
          .join("");
      }}

      async function loadPermissions() {{
        if (!hasPermission("roles.read")) {{
          permissionsBox.innerHTML = '<div class="empty-state">لا تملك صلاحية قراءة كتالوج الصلاحيات.</div>';
          return;
        }}
        const payload = await api("/admin/permissions", {{ method: "GET" }});
        state.permissions = payload.permissions || [];
        renderPermissionsCatalog();
      }}

      function renderRoles() {{
        if (!hasPermission("roles.read")) {{
          rolesList.innerHTML = '<div class="empty-state">لا تملك صلاحية عرض الأدوار.</div>';
          return;
        }}
        if (!state.roles.length) {{
          rolesList.innerHTML = '<div class="empty-state">لا توجد أدوار حالياً.</div>';
          return;
        }}
        rolesList.innerHTML = state.roles
          .map((role) => `
            <article class="role-card">
              <h4>${{escapeHtml(role.display_name || role.name)}}</h4>
              <p>
                <strong>الاسم التقني:</strong> <code>${{escapeHtml(role.name)}}</code><br />
                <strong>عدد المستخدمين:</strong> ${{Number(role.user_count || 0)}}<br />
                <strong>نوع الدور:</strong> ${{role.is_system ? "نظامي" : "مخصص"}}
              </p>
              <p>${{escapeHtml(role.description || "بدون وصف.")}}</p>
              <div class="permission-list">
                ${{(role.permissions || []).length
                  ? role.permissions.map((item) => `<span class="chip">${{escapeHtml(item)}}</span>`).join("")
                  : '<span class="chip">بدون صلاحيات</span>'}}
              </div>
            </article>
          `)
          .join("");
      }}

      async function loadRoles() {{
        if (!hasPermission("roles.read")) {{
          renderRoleSelects();
          renderRoles();
          return;
        }}
        const payload = await api("/admin/roles", {{ method: "GET" }});
        state.roles = payload.roles || [];
        renderRoleSelects();
        renderRoles();
      }}

      function renderUsers() {{
        if (!hasPermission("users.read")) {{
          usersTableBody.innerHTML = '<tr><td colspan="5">لا تملك صلاحية عرض المستخدمين.</td></tr>';
          return;
        }}

        const query = userSearch.value.trim().toLowerCase();
        const rows = state.users.filter((user) => {{
          if (!query) {{
            return true;
          }}
          return [user.full_name, user.email, user.role]
            .some((value) => String(value || "").toLowerCase().includes(query));
        }});

        if (!rows.length) {{
          usersTableBody.innerHTML = '<tr><td colspan="5">لا توجد نتائج مطابقة.</td></tr>';
          return;
        }}

        const canManageUsers = hasPermission("users.manage");
        usersTableBody.innerHTML = rows
          .map((user) => `
            <tr data-user-id="${{escapeHtml(user.id)}}">
              <td>
                <strong>${{escapeHtml(user.full_name)}}</strong>
                <small>${{escapeHtml(user.email)}}</small>
                <small>المعرف: <code>${{escapeHtml(user.id)}}</code></small>
                <small>آخر دخول: ${{escapeHtml(user.last_login_at || "غير متوفر")}}</small>
              </td>
              <td>
                <div class="inline-inputs">
                  <select class="user-role" ${{canManageUsers ? "" : "disabled"}}>
                    ${{renderRoleSelectOptions(user.role)}}
                  </select>
                  <select class="user-active" ${{canManageUsers ? "" : "disabled"}}>
                    <option value="true" ${{user.is_active ? "selected" : ""}}>فعال</option>
                    <option value="false" ${{!user.is_active ? "selected" : ""}}>معطل</option>
                  </select>
                  <span class="pill ${{user.is_active ? "success" : "danger"}}">
                    ${{user.is_active ? "نشط" : "معطل"}}
                  </span>
                </div>
              </td>
              <td>
                <div class="permission-list">
                  ${{(user.permissions || []).length
                    ? user.permissions.map((item) => `<span class="chip">${{escapeHtml(item)}}</span>`).join("")
                    : '<span class="chip">بدون صلاحيات</span>'}}
                </div>
              </td>
              <td>
                <div class="inline-inputs">
                  <input class="user-granted" type="text" placeholder="granted1, granted2" value="${{escapeHtml((user.granted_permissions || []).join(", "))}}" ${{canManageUsers ? "" : "disabled"}} />
                  <input class="user-revoked" type="text" placeholder="revoked1, revoked2" value="${{escapeHtml((user.revoked_permissions || []).join(", "))}}" ${{canManageUsers ? "" : "disabled"}} />
                </div>
              </td>
              <td>
                <div class="actions">
                  <button class="button primary save-user" type="button" ${{canManageUsers ? "" : "disabled"}}>حفظ الحساب</button>
                  <button class="button secondary save-permissions" type="button" ${{canManageUsers ? "" : "disabled"}}>حفظ الصلاحيات</button>
                </div>
              </td>
            </tr>
          `)
          .join("");
      }}

      async function loadUsers() {{
        if (!hasPermission("users.read")) {{
          renderUsers();
          return;
        }}
        const payload = await api("/admin/users", {{ method: "GET" }});
        state.users = payload.users || [];
        renderUsers();
      }}

      function renderActivity() {{
        if (!hasPermission("activity.read")) {{
          activityList.innerHTML = '<div class="empty-state">لا تملك صلاحية عرض سجل النشاطات.</div>';
          activityStats.innerHTML = "";
          return;
        }}
        const localQuery = activitySearch.value.trim().toLowerCase();
        const filteredItems = state.activity.filter((item) => (
          activityMatchesQuickPreset(item) &&
          activityMatchesSearch(item, localQuery)
        ));

        renderActivityStats(filteredItems);

        if (!filteredItems.length) {{
          activityList.innerHTML = '<div class="empty-state">لا توجد نشاطات مطابقة حالياً.</div>';
          return;
        }}
        activityList.innerHTML = filteredItems
          .map((item) => {{
            const tone = getActivityTone(item.action);
            const highlights = getActivityHighlights(item);
            return `
            <article class="log-card ${{tone.className}}">
              <div class="log-head">
                <div class="log-title-stack">
                  <div class="log-badge-row">
                    <span class="pill ${{tone.className}}">${{escapeHtml(tone.label)}}</span>
                    <span class="meta-chip">${{escapeHtml(item.entity_type || "غير محدد")}}</span>
                  </div>
                  <strong>${{escapeHtml(getActivityTitle(item.action))}}</strong>
                  <p class="log-summary">${{escapeHtml(getActivitySummary(item))}}</p>
                </div>
                <div class="log-timebox">
                  <span>${{escapeHtml(formatDateTime(item.created_at))}}</span>
                  <small>${{escapeHtml(item.action)}}</small>
                </div>
              </div>
              <div class="log-badges">
                <span class="meta-chip">المنفذ: <code>${{escapeHtml(item.actor_user_id || "غير محدد")}}</code></span>
                <span class="meta-chip">المستهدف: <code>${{escapeHtml(item.target_user_id || "غير محدد")}}</code></span>
                <span class="meta-chip">الكيان: <code>${{escapeHtml(item.entity_id || "-")}}</code></span>
              </div>
              ${{highlights.length ? `
                <ul class="log-details">
                  ${{highlights.map((line) => `<li>${{escapeHtml(line)}}</li>`).join("")}}
                </ul>
              ` : ""}}
              <details class="log-json">
                <summary>عرض بيانات العملية</summary>
                <pre>${{escapeHtml(JSON.stringify(item.metadata || {{}}, null, 2))}}</pre>
              </details>
            </article>
          `;
          }})
          .join("");
      }}

      async function loadActivity() {{
        if (!hasPermission("activity.read")) {{
          renderActivity();
          return;
        }}
        const params = new URLSearchParams();
        Object.entries(state.activityFilters).forEach(([key, value]) => {{
          if (value !== "" && value !== null && value !== undefined) {{
            params.set(key, String(value));
          }}
        }});
        const payload = await api(`/admin/activity-logs?${{params.toString()}}`, {{ method: "GET" }});
        state.activity = payload.items || [];
        renderActivity();
      }}

      async function refreshEverything() {{
        clearFlash();
        const tasks = [];
        if (hasPermission("admin.summary.read")) {{
          tasks.push(loadSummary());
        }}
        if (hasPermission("roles.read")) {{
          tasks.push(loadPermissions());
          tasks.push(loadRoles());
        }} else {{
          renderRoleSelects();
          renderRoles();
        }}
        if (hasPermission("users.read")) {{
          tasks.push(loadUsers());
        }} else {{
          renderUsers();
        }}
        if (hasPermission("activity.read")) {{
          tasks.push(loadActivity());
        }} else {{
          renderActivity();
        }}
        await Promise.all(tasks);
      }}

      function splitPermissions(value) {{
        return String(value || "")
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean);
      }}

      createUserForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        if (!hasPermission("users.manage")) {{
          setNotice("create-user-notice", "لا تملك صلاحية إنشاء مستخدمين.", "error");
          return;
        }}
        const formData = new FormData(createUserForm);
        const payload = {{
          full_name: String(formData.get("full_name") || "").trim(),
          email: String(formData.get("email") || "").trim(),
          password: String(formData.get("password") || ""),
          role: String(formData.get("role") || "student").trim(),
          is_active: document.getElementById("new-is-active").checked,
        }};

        try {{
          const response = await api("/admin/users", {{
            method: "POST",
            body: JSON.stringify(payload),
          }});
          createUserForm.reset();
          document.getElementById("new-is-active").checked = true;
          renderRoleSelects();
          setNotice("create-user-notice", `تمت إضافة المستخدم ${{response.user.email}} بنجاح.`, "info");
          showFlash("تم إنشاء المستخدم الجديد وتسجيل العملية في السجل.");
          await Promise.all([loadUsers(), loadActivity(), loadSummary().catch(() => {{}})]);
        }} catch (error) {{
          setNotice("create-user-notice", error.message, "error");
        }}
      }});

      createRoleForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        if (!hasPermission("roles.manage")) {{
          setNotice("roles-notice", "لا تملك صلاحية إنشاء الأدوار.", "error");
          return;
        }}
        const formData = new FormData(createRoleForm);
        const permissions = Array.from(
          createRoleForm.querySelectorAll('input[name="permissions"]:checked')
        ).map((node) => node.value);
        const payload = {{
          name: String(formData.get("name") || "").trim(),
          display_name: String(formData.get("display_name") || "").trim(),
          description: String(formData.get("description") || "").trim(),
          permissions,
        }};

        try {{
          await api("/admin/roles", {{
            method: "POST",
            body: JSON.stringify(payload),
          }});
          createRoleForm.reset();
          setNotice("roles-notice", "تم إنشاء الدور الجديد بنجاح.", "info");
          showFlash("تمت إضافة الدور الجديد.");
          await Promise.all([loadRoles(), loadUsers().catch(() => {{}}), loadActivity().catch(() => {{}}), loadSummary().catch(() => {{}})]);
        }} catch (error) {{
          setNotice("roles-notice", error.message, "error");
        }}
      }});

      usersTableBody.addEventListener("click", async (event) => {{
        const button = event.target.closest("button");
        if (!button) {{
          return;
        }}
        const row = button.closest("tr[data-user-id]");
        if (!row) {{
          return;
        }}
        const userId = row.getAttribute("data-user-id");
        const role = row.querySelector(".user-role").value;
        const isActive = row.querySelector(".user-active").value === "true";
        const grantedPermissions = splitPermissions(row.querySelector(".user-granted").value);
        const revokedPermissions = splitPermissions(row.querySelector(".user-revoked").value);

        try {{
          if (button.classList.contains("save-user")) {{
            await api(`/admin/users/${{encodeURIComponent(userId)}}`, {{
              method: "PATCH",
              body: JSON.stringify({{ role, is_active: isActive }}),
            }});
            showFlash("تم تحديث الحساب بنجاح.");
          }} else if (button.classList.contains("save-permissions")) {{
            await api(`/admin/users/${{encodeURIComponent(userId)}}/permissions`, {{
              method: "PUT",
              body: JSON.stringify({{
                granted_permissions: grantedPermissions,
                revoked_permissions: revokedPermissions,
              }}),
            }});
            showFlash("تم تحديث الصلاحيات المخصصة بنجاح.");
          }} else {{
            return;
          }}

          setNotice("users-notice", "تم حفظ التغييرات على المستخدم.", "info");
          await Promise.all([loadUsers(), loadActivity().catch(() => {{}}), loadSummary().catch(() => {{}})]);
        }} catch (error) {{
          setNotice("users-notice", error.message, "error");
        }}
      }});

      activityFilterForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const formData = new FormData(activityFilterForm);
        state.activityFilters = {{
          action: String(formData.get("action") || "").trim(),
          entity_type: String(formData.get("entity_type") || "").trim(),
          actor_user_id: String(formData.get("actor_user_id") || "").trim(),
          target_user_id: String(formData.get("target_user_id") || "").trim(),
          limit: Math.max(1, Math.min(100, Number(formData.get("limit") || 25))),
        }};

        try {{
          await loadActivity();
          setNotice("activity-notice", "تم تحديث نتائج السجل.", "info");
        }} catch (error) {{
          setNotice("activity-notice", error.message, "error");
        }}
      }});

      document.getElementById("reset-activity-filter").addEventListener("click", async () => {{
        activityFilterForm.reset();
        document.getElementById("activity-limit").value = 25;
        state.activityFilters = {{
          limit: 25,
          action: "",
          entity_type: "",
          actor_user_id: "",
          target_user_id: "",
        }};
        state.activityPreset = "all";
        activitySearch.value = "";
        syncActivityPresetButtons();
        try {{
          await loadActivity();
          setNotice("activity-notice", "تمت إعادة ضبط الفلاتر.", "info");
        }} catch (error) {{
          setNotice("activity-notice", error.message, "error");
        }}
      }});

      activityQuickFilters.addEventListener("click", (event) => {{
        const button = event.target.closest("[data-activity-preset]");
        if (!button) {{
          return;
        }}
        state.activityPreset = button.getAttribute("data-activity-preset") || "all";
        syncActivityPresetButtons();
        renderActivity();
      }});

      document.getElementById("refresh-all").addEventListener("click", async () => {{
        try {{
          await refreshEverything();
          showFlash("تم تحديث كل البيانات.");
        }} catch (error) {{
          showFlash(error.message, "error");
        }}
      }});

      document.getElementById("refresh-users").addEventListener("click", async () => {{
        try {{
          await loadUsers();
          setNotice("users-notice", "تم تحديث قائمة المستخدمين.", "info");
        }} catch (error) {{
          setNotice("users-notice", error.message, "error");
        }}
      }});

      document.getElementById("refresh-roles").addEventListener("click", async () => {{
        try {{
          await Promise.all([loadPermissions().catch(() => {{}}), loadRoles()]);
          setNotice("roles-notice", "تم تحديث الأدوار.", "info");
        }} catch (error) {{
          setNotice("roles-notice", error.message, "error");
        }}
      }});

      document.getElementById("refresh-activity").addEventListener("click", async () => {{
        try {{
          await loadActivity();
          setNotice("activity-notice", "تم تحديث سجل النشاطات.", "info");
        }} catch (error) {{
          setNotice("activity-notice", error.message, "error");
        }}
      }});

      userSearch.addEventListener("input", renderUsers);
      activitySearch.addEventListener("input", renderActivity);

      renderSummary();
      renderRoleSelects();
      syncActivityPresetButtons();
      refreshEverything().catch((error) => {{
        showFlash(error.message, "error");
      }});
    </script>
  </body>
</html>
"""
