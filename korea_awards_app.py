# ═══════════════════════════════════════════════════════════════
#  Snowflake Korea Internal Awards 2026
#  Tab 1 👗 AI 베스트 드레서  |  Tab 2 🦶 맨발에 땀나 상
#  🖥️ 전광판 디스플레이 모드  |  🔐 관리자 페이지
# ═══════════════════════════════════════════════════════════════
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json, base64, re
from datetime import datetime
from io import BytesIO

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from snowflake.snowpark.context import get_active_session
    from snowflake.cortex import Complete
    session = get_active_session()
    SNOWFLAKE_AVAILABLE = True
except Exception:
    SNOWFLAKE_AVAILABLE = False
    session = None

# ── PAGE CONFIG ──────────────────────────────────────────────
st.set_page_config(
    page_title="Snowflake Korea Awards 2026",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CONSTANTS ────────────────────────────────────────────────
VISION_MODEL      = "pixtral-large"
MAX_IMG_PX        = 900
THUMB_PX          = 300          # thumbnail stored for admin gallery
JPEG_QUALITY      = 82
SLIDE_DURATION_MS = 10_000
SLIDE_NAMES       = ["intro", "dresser", "steps"]
ADMIN_PASSWORD    = "sf2026admin"   # ← 배포 전 변경 권장

CATEGORIES = [
    ("color_coordination",    "🎨 컬러 코디네이션",   25),
    ("styling_completeness",  "👔 스타일링 완성도",   25),
    ("accessories",           "💎 액세서리 & 포인트",  20),
    ("event_appropriateness", "🏢 행사 분위기 적합성", 15),
    ("creativity",            "✨ 창의성 & 개성",     15),
]
MAX_BASE  = sum(c[2] for c in CATEGORIES)   # 100
BONUS_PTS = 2

# ── SESSION STATE ────────────────────────────────────────────
for k, v in {
    "dresser_lb": [], "steps_lb": [],
    "dress_result": None, "steps_result": None,
    "dress_submitted": False, "steps_submitted": False,
    "tables_ok": False,
    "admin_auth": False,
    "dresser_photos": {},   # name -> thumbnail bytes (for admin gallery)
    "steps_screenshots": {}, # name -> thumbnail bytes
}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── NAME EXTRACTION ──────────────────────────────────────────
def extract_name_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    stem = re.sub(r"[\(\[\{].*?[\)\]\}]", "", stem)
    stem = re.sub(r"[_\-\.]+", " ", stem)
    return re.sub(r"\s+", " ", stem).strip().title()

# ══════════════════════════════════════════════════════════════
#  SNOWFLAKE TABLE HELPERS
# ══════════════════════════════════════════════════════════════
def init_tables() -> bool:
    if not SNOWFLAKE_AVAILABLE:
        return False
    try:
        session.sql("""
            CREATE TABLE IF NOT EXISTS DRESSER_LEADERBOARD (
                ID INTEGER AUTOINCREMENT PRIMARY KEY,
                NAME VARCHAR(100),
                COLOR_SCORE INTEGER, STYLING_SCORE INTEGER,
                ACCESSORIES_SCORE INTEGER, APPROP_SCORE INTEGER,
                CREATIVITY_SCORE INTEGER, BONUS BOOLEAN DEFAULT FALSE,
                TOTAL_SCORE INTEGER, STYLE_TITLE VARCHAR(300),
                OVERALL_COMMENT TEXT,
                SUBMITTED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP())
        """).collect()
        session.sql("""
            CREATE TABLE IF NOT EXISTS STEPS_LEADERBOARD (
                ID INTEGER AUTOINCREMENT PRIMARY KEY,
                NAME VARCHAR(100), STEPS INTEGER,
                SUBMITTED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP())
        """).collect()
        return True
    except Exception:
        return False

if not st.session_state.tables_ok:
    st.session_state.tables_ok = init_tables()

# ── Write helpers ─────────────────────────────────────────────
def save_dresser(name, r, thumb_bytes=None):
    sc    = r["scores"]
    bonus = r.get("bonus", False)
    total = sum(sc.values()) + (BONUS_PTS if bonus else 0)
    entry = dict(name=name,
        color_score=sc.get("color_coordination",0),
        styling_score=sc.get("styling_completeness",0),
        accessories_score=sc.get("accessories",0),
        approp_score=sc.get("event_appropriateness",0),
        creativity_score=sc.get("creativity",0),
        bonus=bonus, total_score=total,
        style_title=r.get("style_title",""),
        overall_comment=r.get("overall_comment",""),
        submitted_at=datetime.now().strftime("%H:%M"))
    st.session_state.dresser_lb.append(entry)
    if thumb_bytes:
        st.session_state.dresser_photos[name] = thumb_bytes
    if st.session_state.tables_ok:
        try:
            session.sql("""
                INSERT INTO DRESSER_LEADERBOARD
                (NAME,COLOR_SCORE,STYLING_SCORE,ACCESSORIES_SCORE,APPROP_SCORE,
                 CREATIVITY_SCORE,BONUS,TOTAL_SCORE,STYLE_TITLE,OVERALL_COMMENT)
                VALUES(?,?,?,?,?,?,?,?,?,?)
            """, params=[name, entry["color_score"], entry["styling_score"],
                         entry["accessories_score"], entry["approp_score"],
                         entry["creativity_score"], bonus, total,
                         entry["style_title"], entry["overall_comment"]]).collect()
        except Exception:
            pass

def save_steps(name, steps, thumb_bytes=None):
    entry = dict(name=name, steps=steps, submitted_at=datetime.now().strftime("%H:%M"))
    st.session_state.steps_lb.append(entry)
    if thumb_bytes:
        st.session_state.steps_screenshots[name] = thumb_bytes
    if st.session_state.tables_ok:
        try:
            session.sql("INSERT INTO STEPS_LEADERBOARD (NAME,STEPS) VALUES(?,?)",
                        params=[name, steps]).collect()
        except Exception:
            pass

# ── Read helpers (public leaderboard) ────────────────────────
def load_dresser_lb() -> list:
    if st.session_state.tables_ok:
        try:
            rows = session.sql(
                "SELECT NAME,COLOR_SCORE,STYLING_SCORE,ACCESSORIES_SCORE,APPROP_SCORE,"
                "CREATIVITY_SCORE,BONUS,TOTAL_SCORE,STYLE_TITLE,"
                "TO_CHAR(SUBMITTED_AT,'HH24:MI') FROM DRESSER_LEADERBOARD "
                "ORDER BY TOTAL_SCORE DESC").collect()
            return [dict(name=r[0],color_score=r[1],styling_score=r[2],
                         accessories_score=r[3],approp_score=r[4],creativity_score=r[5],
                         bonus=r[6],total_score=r[7],style_title=r[8],submitted_at=r[9])
                    for r in rows]
        except Exception:
            pass
    return sorted(st.session_state.dresser_lb, key=lambda x: x["total_score"], reverse=True)

def load_steps_lb() -> list:
    if st.session_state.tables_ok:
        try:
            rows = session.sql(
                "SELECT NAME,STEPS,TO_CHAR(SUBMITTED_AT,'HH24:MI') "
                "FROM STEPS_LEADERBOARD ORDER BY STEPS DESC").collect()
            return [dict(name=r[0],steps=r[1],submitted_at=r[2]) for r in rows]
        except Exception:
            pass
    return sorted(st.session_state.steps_lb, key=lambda x: x["steps"], reverse=True)

# ── Admin read helpers (with IDs, ordered by submit time) ────
def admin_load_dresser() -> list:
    if st.session_state.tables_ok:
        try:
            rows = session.sql(
                "SELECT ID,NAME,COLOR_SCORE,STYLING_SCORE,ACCESSORIES_SCORE,APPROP_SCORE,"
                "CREATIVITY_SCORE,BONUS,TOTAL_SCORE,STYLE_TITLE,OVERALL_COMMENT,"
                "TO_CHAR(SUBMITTED_AT,'YYYY-MM-DD HH24:MI:SS') "
                "FROM DRESSER_LEADERBOARD ORDER BY SUBMITTED_AT DESC").collect()
            return [dict(id=r[0],name=r[1],color_score=r[2],styling_score=r[3],
                         accessories_score=r[4],approp_score=r[5],creativity_score=r[6],
                         bonus=bool(r[7]),total_score=r[8],style_title=r[9],
                         overall_comment=r[10],submitted_at=r[11]) for r in rows]
        except Exception:
            pass
    return [dict(id=i, **e) for i, e in enumerate(st.session_state.dresser_lb)]

def admin_load_steps() -> list:
    if st.session_state.tables_ok:
        try:
            rows = session.sql(
                "SELECT ID,NAME,STEPS,TO_CHAR(SUBMITTED_AT,'YYYY-MM-DD HH24:MI:SS') "
                "FROM STEPS_LEADERBOARD ORDER BY SUBMITTED_AT DESC").collect()
            return [dict(id=r[0],name=r[1],steps=r[2],submitted_at=r[3]) for r in rows]
        except Exception:
            pass
    return [dict(id=i, **e) for i, e in enumerate(st.session_state.steps_lb)]

# ── Admin mutate helpers ──────────────────────────────────────
def admin_delete_dresser(entry_id):
    if st.session_state.tables_ok:
        try:
            session.sql("DELETE FROM DRESSER_LEADERBOARD WHERE ID=?",
                        params=[int(entry_id)]).collect()
        except Exception:
            pass
    st.session_state.dresser_lb = [r for r in st.session_state.dresser_lb
                                    if r.get("id") != entry_id]

def admin_update_dresser(entry_id, color, styling, accessories, approp, creativity,
                          bonus, style_title, overall_comment):
    total = color + styling + accessories + approp + creativity + (BONUS_PTS if bonus else 0)
    if st.session_state.tables_ok:
        try:
            session.sql("""
                UPDATE DRESSER_LEADERBOARD SET
                    COLOR_SCORE=?, STYLING_SCORE=?, ACCESSORIES_SCORE=?,
                    APPROP_SCORE=?, CREATIVITY_SCORE=?, BONUS=?, TOTAL_SCORE=?,
                    STYLE_TITLE=?, OVERALL_COMMENT=?
                WHERE ID=?
            """, params=[color, styling, accessories, approp, creativity,
                         bonus, total, style_title, overall_comment,
                         int(entry_id)]).collect()
        except Exception:
            pass

def admin_delete_steps(entry_id):
    if st.session_state.tables_ok:
        try:
            session.sql("DELETE FROM STEPS_LEADERBOARD WHERE ID=?",
                        params=[int(entry_id)]).collect()
        except Exception:
            pass
    st.session_state.steps_lb = [r for r in st.session_state.steps_lb
                                   if r.get("id") != entry_id]

def admin_update_steps(entry_id, steps):
    if st.session_state.tables_ok:
        try:
            session.sql("UPDATE STEPS_LEADERBOARD SET STEPS=? WHERE ID=?",
                        params=[int(steps), int(entry_id)]).collect()
        except Exception:
            pass

# ── Image helpers ─────────────────────────────────────────────
def prepare_image(f, max_px=MAX_IMG_PX) -> bytes:
    raw = f.read()
    if not PIL_AVAILABLE:
        return raw
    img = PILImage.open(BytesIO(raw)).convert("RGB")
    img.thumbnail((max_px, max_px), PILImage.LANCZOS)
    buf = BytesIO(); img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()

def make_thumb(img_bytes: bytes) -> bytes:
    if not PIL_AVAILABLE:
        return img_bytes
    img = PILImage.open(BytesIO(img_bytes)).convert("RGB")
    img.thumbnail((THUMB_PX, THUMB_PX), PILImage.LANCZOS)
    buf = BytesIO(); img.save(buf, format="JPEG", quality=75)
    return buf.getvalue()

def to_b64(b): return base64.b64encode(b).decode()
def parse_json_safe(t):
    m = re.search(r"\{.*\}", t, re.DOTALL)
    if m: return json.loads(m.group())
    raise ValueError("No JSON in response")

# ── Cortex calls ──────────────────────────────────────────────
def analyze_fashion(img_bytes):
    b64 = to_b64(img_bytes)
    prompt = (
        "당신은 패션 전문가이자 AI 심사위원입니다. Snowflake Korea World Tour 행사에서 팀원들이 "
        "동일한 Snowflake 유니폼 티셔츠를 착용하고 있습니다. 유니폼 외 스타일링을 평가해주세요.\n\n"
        "1. color_coordination 0-25점\n2. styling_completeness 0-25점\n"
        "3. accessories 0-20점 (Snowflake 굿즈 시 bonus=true)\n"
        "4. event_appropriateness 0-15점\n5. creativity 0-15점\n\n"
        '{"scores":{"color_coordination":<0-25>,"styling_completeness":<0-25>,'
        '"accessories":<0-20>,"event_appropriateness":<0-15>,"creativity":<0-15>},'
        '"bonus":<true/false>,'
        '"comments":{"color_coordination":"<ko>","styling_completeness":"<ko>",'
        '"accessories":"<ko>","event_appropriateness":"<ko>","creativity":"<ko>"},'
        '"overall_comment":"<총평 2-3문장 한국어>","style_title":"<한마디 타이틀>"}'
    )
    messages = [{"role":"user","content":[
        {"type":"text","text":prompt},
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}]
    raw = Complete(VISION_MODEL, messages)
    return parse_json_safe(raw if isinstance(raw, str) else str(raw))

def extract_steps(img_bytes):
    b64 = to_b64(img_bytes)
    prompt = ('이미지에서 오늘 총 걸음 수를 읽어주세요.\n'
              '{"steps":<정수>,"confidence":"<high/medium/low>","note":"<참고사항>"}')
    messages = [{"role":"user","content":[
        {"type":"text","text":prompt},
        {"type":"image_url","image_url":{"url":f"data:image/jpeg;base64,{b64}"}}]}]
    raw = Complete(VISION_MODEL, messages)
    return parse_json_safe(raw if isinstance(raw, str) else str(raw))

# ── Misc UI helpers ───────────────────────────────────────────
def rank_emoji(i): return ["🥇","🥈","🥉"][i] if i < 3 else f"{i+1}위"

def score_bar_html(label, score, max_score, comment=""):
    pct   = int(score/max_score*100)
    color = "#F5A623" if pct>=80 else "#29B5E8" if pct>=55 else "#8AAFCC"
    h = (f'<div style="margin-bottom:14px">'
         f'<div style="display:flex;justify-content:space-between;margin:4px 0">'
         f'<span style="color:#CBD5E0;font-size:.88rem">{label}</span>'
         f'<span style="color:#F5A623;font-weight:700">{score}'
         f'<span style="color:#8AAFCC;font-size:.8rem">/{max_score}</span></span></div>'
         f'<div style="background:rgba(255,255,255,.08);border-radius:6px;height:7px;margin:5px 0 3px">'
         f'<div style="background:{color};width:{pct}%;height:100%;border-radius:6px"></div></div>')
    if comment:
        h += f'<div style="color:#8AAFCC;font-size:.8rem;font-style:italic">{comment}</div>'
    return h + "</div>"

def name_chip_html(name, filename):
    return (f'<div style="display:inline-flex;align-items:center;gap:8px;'
            f'background:rgba(41,181,232,.12);border:1px solid rgba(41,181,232,.4);'
            f'border-radius:30px;padding:6px 16px;font-size:1rem;font-weight:700;'
            f'color:#FFFFFF;margin-bottom:6px">👤 {name}</div>'
            f'<div style="color:#8AAFCC;font-size:.78rem;margin-bottom:14px;'
            f'font-style:italic">📁 파일명에서 추출: <code>{filename}</code></div>')


# ══════════════════════════════════════════════════════════════
#  🖥️  DISPLAY MODE
# ══════════════════════════════════════════════════════════════
DISPLAY_CSS = """<style>
[data-testid="stHeader"],[data-testid="stToolbar"],
[data-testid="stSidebar"],#MainMenu,footer{display:none!important}
.main .block-container{padding:0!important;max-width:100vw!important;min-height:100vh}
.stApp{background:#050E1A!important}
@keyframes countdown{from{width:100%}to{width:0%}}
.prog-track{position:fixed;top:0;left:0;width:100%;height:5px;
  background:rgba(255,255,255,.08);z-index:9999}
.prog-fill{height:100%;background:linear-gradient(90deg,#29B5E8,#F5A623);
  animation:countdown VAR_DURATIONms linear forwards}
.slide-dots{display:flex;justify-content:center;gap:10px;padding:18px 0 0}
.dot{width:9px;height:9px;border-radius:50%;background:rgba(255,255,255,.18)}
.dot.on{background:#29B5E8;width:28px;border-radius:5px}
.slide-body{padding:40px 80px 20px;min-height:90vh;display:flex;flex-direction:column}
.slide-title{font-size:2.6rem;font-weight:900;color:#FFFFFF;margin-bottom:4px;line-height:1.2}
.slide-sub{color:#8AAFCC;font-size:1.05rem;margin-bottom:36px}
.live-badge{display:inline-flex;align-items:center;gap:7px;
  background:rgba(239,68,68,.15);border:1px solid rgba(239,68,68,.4);
  border-radius:20px;padding:3px 13px;color:#FC8181;font-size:.8rem;font-weight:700;letter-spacing:.05em}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.2}}
.live-dot{width:8px;height:8px;border-radius:50%;background:#FC8181;animation:pulse 1.4s infinite}
.lb-row-disp{display:flex;align-items:center;background:rgba(255,255,255,.04);
  border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:20px 28px;margin:10px 0}
.lb-row-disp.gold{background:rgba(245,166,35,.1);border-color:rgba(245,166,35,.35)}
.ld-rank{font-size:2.2rem;min-width:64px}.ld-info{flex:1}
.ld-name{font-size:1.9rem;font-weight:800;color:#FFFFFF;line-height:1.2}
.ld-meta{color:#8AAFCC;font-size:.9rem;margin-top:3px}
.ld-score{font-size:2.2rem;font-weight:900;color:#F5A623;min-width:130px;text-align:right}
.hbar-track{height:8px;background:rgba(255,255,255,.08);border-radius:4px;margin-top:8px;overflow:hidden}
.hbar-fill{height:100%;border-radius:4px;background:linear-gradient(90deg,#29B5E8,#1E3A5F)}
.hbar-fill-gold{background:linear-gradient(90deg,#F5A623,#FFD700)}
.intro-wrap{display:flex;flex-direction:column;align-items:center;justify-content:center;
  min-height:85vh;text-align:center}
.intro-icon{font-size:6rem;margin-bottom:24px}
.intro-title{font-size:3.4rem;font-weight:900;color:#FFFFFF;line-height:1.2;margin-bottom:14px}
.intro-event{color:#29B5E8;font-size:1.5rem;font-weight:600;margin-bottom:20px}
.intro-hint{color:#8AAFCC;font-size:.95rem;background:rgba(255,255,255,.04);
  border:1px solid rgba(41,181,232,.2);border-radius:30px;padding:8px 24px}
</style>"""

def _auto_advance_js(next_idx):
    components.html(
        f"""<script>setTimeout(function(){{
        var u=new URL(window.top.location.href);
        u.searchParams.set('mode','display');
        u.searchParams.set('slide','{next_idx}');
        window.top.location.href=u.toString();
        }},{SLIDE_DURATION_MS});</script>""", height=0, scrolling=False)

def _slide_chrome(slide_idx):
    n    = len(SLIDE_NAMES)
    dots = "".join(f'<div class="dot{"  on" if i==slide_idx else ""}"></div>' for i in range(n))
    st.markdown(
        DISPLAY_CSS.replace("VAR_DURATION", str(SLIDE_DURATION_MS)) +
        f'<div class="prog-track"><div class="prog-fill"></div></div>'
        f'<div class="slide-dots">{dots}</div>', unsafe_allow_html=True)
    l, _, r = st.columns([2,5,2])
    with l:
        st.markdown('<div class="live-badge" style="margin-top:8px">'
                    '<span class="live-dot"></span>LIVE</div>', unsafe_allow_html=True)
    with r:
        st.markdown(f'<div style="color:#8AAFCC;font-size:.8rem;text-align:right;'
                    f'padding-top:10px">🕐 {datetime.now().strftime("%H:%M:%S")}</div>',
                    unsafe_allow_html=True)

def _render_intro_slide():
    st.markdown('<div class="intro-wrap"><div class="intro-icon">🏆</div>'
                '<div class="intro-title">Snowflake Korea<br>Internal Awards 2026</div>'
                '<div class="intro-event">Snowflake World Tour Seoul</div>'
                '<div class="intro-hint">📊 실시간 리더보드 · Powered by Snowflake Cortex AI ✨'
                '</div></div>', unsafe_allow_html=True)

def _render_dresser_slide():
    lb = load_dresser_lb()
    st.markdown('<div class="slide-body"><div class="slide-title">👗 AI 베스트 드레서 리더보드</div>'
                '<div class="slide-sub">Snowflake 유니폼 스타일링 AI 채점 결과</div>', unsafe_allow_html=True)
    if not lb:
        st.markdown('<div style="text-align:center;color:#8AAFCC;padding:80px 0;font-size:1.5rem">'
                    '📭 아직 제출된 결과가 없습니다</div></div>', unsafe_allow_html=True); return
    for i, row in enumerate(lb[:5]):
        pct = int(row["total_score"]/(MAX_BASE+BONUS_PTS)*100)
        gold = " gold" if i==0 else ""
        bar  = "hbar-fill-gold" if i==0 else "hbar-fill"
        rank = ["🥇","🥈","🥉","4위 ","5위 "][i] if i<5 else f"{i+1}위"
        bh   = ('<span style="background:#F5A623;color:#0D1B2A;border-radius:10px;'
                'font-size:.7rem;font-weight:700;padding:1px 8px;margin-left:8px">+2</span>'
                ) if row.get("bonus") else ""
        th   = f'<div class="ld-meta">✨ {row["style_title"]}</div>' if row.get("style_title") else ""
        st.markdown(
            f'<div class="lb-row-disp{gold}">'
            f'<div class="ld-rank">{rank}</div>'
            f'<div class="ld-info"><div class="ld-name">{row["name"]}{bh}</div>'
            f'{th}<div class="hbar-track"><div class="{bar}" style="width:{pct}%"></div></div></div>'
            f'<div class="ld-score">{row["total_score"]}'
            f'<span style="font-size:1.1rem;color:#8AAFCC;font-weight:400">점</span></div></div>',
            unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def _render_steps_slide():
    lb = load_steps_lb()
    st.markdown('<div class="slide-body"><div class="slide-title">🦶 맨발에 땀나 리더보드</div>'
                '<div class="slide-sub">행사 당일 만보기 챔피언 순위</div>', unsafe_allow_html=True)
    if not lb:
        st.markdown('<div style="text-align:center;color:#8AAFCC;padding:80px 0;font-size:1.5rem">'
                    '📭 아직 제출된 기록이 없습니다</div></div>', unsafe_allow_html=True); return
    mx = max(r["steps"] for r in lb)
    for i, row in enumerate(lb[:5]):
        pct  = int(row["steps"]/mx*100) if mx else 0
        gold = " gold" if i==0 else ""
        bar  = "hbar-fill-gold" if i==0 else "hbar-fill"
        rank = ["🥇","🥈","🥉","4위 ","5위 "][i] if i<5 else f"{i+1}위"
        st.markdown(
            f'<div class="lb-row-disp{gold}">'
            f'<div class="ld-rank">{rank}</div>'
            f'<div class="ld-info"><div class="ld-name">{row["name"]}{"  👑" if i==0 else ""}</div>'
            f'<div class="hbar-track"><div class="{bar}" style="width:{pct}%"></div></div></div>'
            f'<div class="ld-score" style="font-size:1.9rem">{row["steps"]:,}'
            f'<br><span style="font-size:.9rem;color:#8AAFCC;font-weight:400">걸음</span></div></div>',
            unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_display_mode():
    n         = len(SLIDE_NAMES)
    idx       = int(st.query_params.get("slide","0")) % n
    current   = SLIDE_NAMES[idx]
    next_idx  = (idx+1) % n
    _slide_chrome(idx)
    _auto_advance_js(next_idx)
    if   current=="intro":   _render_intro_slide()
    elif current=="dresser": _render_dresser_slide()
    elif current=="steps":   _render_steps_slide()
    st.markdown("<br>", unsafe_allow_html=True)
    c1,c2,c3,c4 = st.columns([1,4,1,1])
    with c1:
        if st.button("◀ 이전", key="dp"):
            st.query_params["slide"]=str((idx-1)%n); st.rerun()
    with c2:
        labels={"intro":"🏆 인트로","dresser":"👗 드레서","steps":"🦶 만보기"}
        st.markdown(f'<div style="text-align:center;color:#8AAFCC;font-size:.9rem;padding-top:8px">'
                    f'{labels.get(current,"")} ({idx+1}/{n})</div>', unsafe_allow_html=True)
    with c3:
        if st.button("다음 ▶", key="dn"):
            st.query_params["slide"]=str(next_idx); st.rerun()
    with c4:
        if st.button("✕ 종료", key="de"):
            st.query_params.clear(); st.rerun()


# ══════════════════════════════════════════════════════════════
#  🔐  ADMIN MODE
# ══════════════════════════════════════════════════════════════
ADMIN_CSS = """<style>
[data-testid="stHeader"],[data-testid="stToolbar"],
#MainMenu,footer{visibility:hidden}
.stApp{background:linear-gradient(150deg,#080F1A,#0F1E35)!important}
.admin-hero{background:linear-gradient(90deg,#1B1F2E,#080F1A);
  border-left:6px solid #E53E3E;border-radius:14px;padding:20px 28px;margin-bottom:20px}
.admin-hero h1{margin:0;font-size:1.7rem;color:#FFFFFF}
.admin-hero p{margin:4px 0 0;color:#FC8181;font-size:.9rem}
.a-panel{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.1);
  border-radius:12px;padding:20px;margin-bottom:14px}
.a-label{color:#FC8181;font-weight:700;font-size:.8rem;letter-spacing:.08em;
  text-transform:uppercase;border-bottom:1px solid rgba(252,129,129,.2);
  padding-bottom:6px;margin-bottom:14px}
.entry-card{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.08);
  border-radius:12px;padding:18px 20px;margin:10px 0}
.entry-name{font-size:1.1rem;font-weight:700;color:#FFFFFF;margin-bottom:4px}
.entry-meta{color:#8AAFCC;font-size:.82rem}
.score-chip{display:inline-block;background:rgba(41,181,232,.15);
  border:1px solid rgba(41,181,232,.3);border-radius:6px;
  padding:2px 8px;font-size:.8rem;color:#29B5E8;margin:2px}
.total-chip{background:rgba(245,166,35,.15);border-color:rgba(245,166,35,.4);
  color:#F5A623;font-weight:700}
.del-zone{background:rgba(239,68,68,.06);border:1px solid rgba(239,68,68,.2);
  border-radius:10px;padding:14px 18px;margin-top:12px}
</style>"""

def _admin_login():
    st.markdown(ADMIN_CSS, unsafe_allow_html=True)
    st.markdown("""
    <div style="display:flex;align-items:center;justify-content:center;min-height:80vh">
      <div style="width:400px;text-align:center">
        <div style="font-size:3rem;margin-bottom:16px">🔐</div>
        <div style="font-size:1.6rem;font-weight:800;color:#FFFFFF;margin-bottom:6px">관리자 페이지</div>
        <div style="color:#8AAFCC;font-size:.9rem;margin-bottom:28px">
          Snowflake Korea Awards 2026</div>
      </div>
    </div>""", unsafe_allow_html=True)
    _, mid, _ = st.columns([1,2,1])
    with mid:
        pw = st.text_input("관리자 비밀번호", type="password", key="admin_pw_input",
                           placeholder="비밀번호를 입력하세요")
        if st.button("🔓 로그인", key="admin_login_btn", use_container_width=True):
            if pw == ADMIN_PASSWORD:
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")

def _admin_dresser_tab():
    """Admin panel for dresser submissions."""
    entries = admin_load_dresser()
    photos  = st.session_state.get("dresser_photos", {})

    # ── 사진 갤러리 ──────────────────────────────────────────
    if photos:
        st.markdown('<div class="a-panel"><div class="a-label">📸 제출 사진 갤러리</div>',
                    unsafe_allow_html=True)
        cols = st.columns(min(len(photos), 5))
        for i, (name, thumb) in enumerate(photos.items()):
            with cols[i % len(cols)]:
                st.image(thumb, caption=name, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("💡 현재 세션에서 제출된 사진이 없습니다. (사진은 세션 내에서만 보관됩니다)")

    # ── 전체 목록 ─────────────────────────────────────────────
    st.markdown('<div class="a-panel"><div class="a-label">📋 전체 제출 현황</div>',
                unsafe_allow_html=True)
    if not entries:
        st.info("제출된 항목이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    df_view = pd.DataFrame([{
        "ID": e["id"], "이름": e["name"],
        "🎨컬러": e["color_score"], "👔스타일": e["styling_score"],
        "💎액세서리": e["accessories_score"], "🏢적합성": e["approp_score"],
        "✨창의성": e["creativity_score"],
        "굿즈": "✅" if e.get("bonus") else "—",
        "총점": e["total_score"], "제출시각": e.get("submitted_at",""),
    } for e in entries])
    st.dataframe(df_view, hide_index=True, use_container_width=True,
                 column_config={"총점": st.column_config.ProgressColumn(
                     "총점", min_value=0, max_value=MAX_BASE+BONUS_PTS, format="%d")})
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 점수 수정 ─────────────────────────────────────────────
    st.markdown('<div class="a-panel"><div class="a-label">✏️ 점수 수정</div>',
                unsafe_allow_html=True)
    names_map = {f"[{e['id']}] {e['name']}": e for e in entries}
    sel_key   = st.selectbox("수정할 참가자 선택", ["— 선택 —"] + list(names_map.keys()),
                              key="admin_d_sel")
    if sel_key != "— 선택 —":
        e = names_map[sel_key]
        with st.form(f"edit_form_{e['id']}"):
            st.markdown(f'<div class="entry-name">✏️ {e["name"]} 점수 수정</div>',
                        unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                new_color   = st.slider("🎨 컬러 코디네이션",   0, 25, e["color_score"])
                new_styling = st.slider("👔 스타일링 완성도",   0, 25, e["styling_score"])
                new_acc     = st.slider("💎 액세서리 & 포인트", 0, 20, e["accessories_score"])
            with c2:
                new_approp  = st.slider("🏢 행사 분위기 적합성",0, 15, e["approp_score"])
                new_creat   = st.slider("✨ 창의성 & 개성",     0, 15, e["creativity_score"])
                new_bonus   = st.checkbox("🎁 Snowflake 굿즈 보너스 (+2점)",
                                          value=bool(e.get("bonus")))
            new_total = new_color+new_styling+new_acc+new_approp+new_creat+(BONUS_PTS if new_bonus else 0)
            st.markdown(f'<div style="color:#F5A623;font-weight:700;font-size:1rem;'
                        f'margin:8px 0">수정 후 총점: {new_total}점</div>', unsafe_allow_html=True)
            new_title   = st.text_input("✨ 스타일 타이틀", value=e.get("style_title",""))
            new_comment = st.text_area("🤖 AI 코멘트", value=e.get("overall_comment",""), height=80)
            if st.form_submit_button("💾 저장", use_container_width=True):
                admin_update_dresser(e["id"], new_color, new_styling, new_acc,
                                      new_approp, new_creat, new_bonus, new_title, new_comment)
                st.success(f"✅ {e['name']} 님의 점수가 수정됐습니다! (총점: {new_total}점)")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 항목 삭제 ─────────────────────────────────────────────
    st.markdown('<div class="a-panel"><div class="a-label">🗑️ 항목 삭제</div>',
                unsafe_allow_html=True)
    del_key = st.selectbox("삭제할 참가자 선택", ["— 선택 —"] + list(names_map.keys()),
                            key="admin_d_del")
    if del_key != "— 선택 —":
        e   = names_map[del_key]
        st.markdown(
            f'<div class="del-zone">'
            f'<span style="color:#FC8181;font-weight:600">⚠️ 삭제 대상:</span> '
            f'<strong>{e["name"]}</strong> — 총점 {e["total_score"]}점 · {e.get("submitted_at","")}'
            f'</div>', unsafe_allow_html=True)
        confirm = st.checkbox("삭제를 확인합니다. 이 작업은 되돌릴 수 없습니다.", key="admin_d_confirm")
        if confirm:
            if st.button("🗑️ 최종 삭제", key="admin_d_del_btn", type="primary",
                         use_container_width=False):
                admin_delete_dresser(e["id"])
                st.success(f"✅ {e['name']} 님의 데이터가 삭제됐습니다.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def _admin_steps_tab():
    """Admin panel for steps submissions."""
    entries     = admin_load_steps()
    screenshots = st.session_state.get("steps_screenshots", {})

    if screenshots:
        st.markdown('<div class="a-panel"><div class="a-label">📱 제출 스크린샷 갤러리</div>',
                    unsafe_allow_html=True)
        cols = st.columns(min(len(screenshots), 5))
        for i, (name, thumb) in enumerate(screenshots.items()):
            with cols[i % len(cols)]:
                st.image(thumb, caption=name, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.info("💡 현재 세션에서 제출된 스크린샷이 없습니다.")

    st.markdown('<div class="a-panel"><div class="a-label">📋 전체 제출 현황</div>',
                unsafe_allow_html=True)
    if not entries:
        st.info("제출된 항목이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    df_s = pd.DataFrame([{
        "ID": e["id"], "이름": e["name"],
        "걸음 수": e["steps"], "제출시각": e.get("submitted_at",""),
    } for e in entries])
    st.dataframe(df_s, hide_index=True, use_container_width=True,
                 column_config={"걸음 수": st.column_config.ProgressColumn(
                     "걸음 수", min_value=0,
                     max_value=max(e["steps"] for e in entries) if entries else 1, format="%d")})
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 걸음수 수정 ───────────────────────────────────────────
    st.markdown('<div class="a-panel"><div class="a-label">✏️ 걸음수 수정</div>',
                unsafe_allow_html=True)
    names_map = {f"[{e['id']}] {e['name']}": e for e in entries}
    sel_s     = st.selectbox("수정할 참가자 선택", ["— 선택 —"] + list(names_map.keys()),
                              key="admin_s_sel")
    if sel_s != "— 선택 —":
        e = names_map[sel_s]
        with st.form(f"steps_edit_{e['id']}"):
            st.markdown(f'<div class="entry-name">✏️ {e["name"]} 걸음수 수정</div>',
                        unsafe_allow_html=True)
            new_steps = st.number_input("걸음 수", value=int(e["steps"]),
                                         min_value=0, max_value=200000, step=1)
            if st.form_submit_button("💾 저장", use_container_width=True):
                admin_update_steps(e["id"], new_steps)
                st.success(f"✅ {e['name']} 님의 걸음 수가 {new_steps:,}걸음으로 수정됐습니다!")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    # ── 항목 삭제 ─────────────────────────────────────────────
    st.markdown('<div class="a-panel"><div class="a-label">🗑️ 항목 삭제</div>',
                unsafe_allow_html=True)
    del_s = st.selectbox("삭제할 참가자 선택", ["— 선택 —"] + list(names_map.keys()),
                          key="admin_s_del")
    if del_s != "— 선택 —":
        e = names_map[del_s]
        st.markdown(
            f'<div class="del-zone">'
            f'<span style="color:#FC8181;font-weight:600">⚠️ 삭제 대상:</span> '
            f'<strong>{e["name"]}</strong> — {e["steps"]:,} 걸음 · {e.get("submitted_at","")}'
            f'</div>', unsafe_allow_html=True)
        confirm_s = st.checkbox("삭제를 확인합니다.", key="admin_s_confirm")
        if confirm_s:
            if st.button("🗑️ 최종 삭제", key="admin_s_del_btn", type="primary",
                         use_container_width=False):
                admin_delete_steps(e["id"])
                st.success(f"✅ {e['name']} 님의 데이터가 삭제됐습니다.")
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def render_admin_mode():
    st.markdown(ADMIN_CSS, unsafe_allow_html=True)

    if not st.session_state.admin_auth:
        _admin_login()
        return

    # ── Admin header ─────────────────────────────────────────
    h_col, logout_col = st.columns([5,1])
    with h_col:
        st.markdown(
            '<div class="admin-hero">'
            '<h1>🔐 관리자 페이지</h1>'
            '<p>Snowflake Korea Awards 2026 · 데이터 조회 / 수정 / 삭제</p>'
            '</div>', unsafe_allow_html=True)
    with logout_col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 로그아웃", key="admin_logout"):
            st.session_state.admin_auth = False
            st.query_params.clear()
            st.rerun()

    # ── Stats summary ─────────────────────────────────────────
    d_count = len(admin_load_dresser())
    s_count = len(admin_load_steps())
    m1, m2, m3 = st.columns(3)
    m1.metric("👗 드레서 제출 수",  f"{d_count}명")
    m2.metric("🦶 만보기 제출 수",  f"{s_count}명")
    m3.metric("📊 전체 제출 수",    f"{d_count + s_count}건")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────
    at1, at2 = st.tabs(["👗 드레서 관리", "🦶 만보기 관리"])
    with at1:
        _admin_dresser_tab()
    with at2:
        _admin_steps_tab()

    # ── Bottom nav ────────────────────────────────────────────
    st.markdown("---")
    bc1, bc2 = st.columns(2)
    with bc1:
        if st.button("🖥️ 전광판 모드로 전환", use_container_width=True):
            st.query_params["mode"]  = "display"
            st.query_params["slide"] = "0"
            st.rerun()
    with bc2:
        if st.button("🏠 일반 모드로 돌아가기", use_container_width=True):
            st.query_params.clear()
            st.rerun()


# ══════════════════════════════════════════════════════════════
#  MODE ROUTER
# ══════════════════════════════════════════════════════════════
mode = st.query_params.get("mode", "")
if mode == "display":
    render_display_mode()
    st.stop()
if mode == "admin":
    render_admin_mode()
    st.stop()


# ══════════════════════════════════════════════════════════════
#  NORMAL MODE CSS
# ══════════════════════════════════════════════════════════════
st.markdown("""
<style>
  .stApp{background:linear-gradient(150deg,#0D1B2A 0%,#1B3253 100%);color:#FFFFFF}
  [data-testid="stAppViewContainer"],[data-testid="stHeader"]{background:transparent}
  #MainMenu,footer,[data-testid="stToolbar"]{visibility:hidden}
  .hero{background:linear-gradient(90deg,#1B3253,#0D1B2A);border-left:6px solid #F5A623;
    border-radius:14px;padding:22px 30px 18px;margin-bottom:20px}
  .hero h1{margin:0;font-size:1.9rem;color:#FFFFFF}
  .hero p{margin:6px 0 0;color:#8AAFCC;font-size:.95rem}
  .display-banner{background:linear-gradient(90deg,rgba(245,166,35,.12),rgba(41,181,232,.08));
    border:1px solid rgba(245,166,35,.35);border-radius:12px;padding:14px 22px;
    display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}
  .display-banner-text{color:#F5A623;font-weight:700;font-size:.95rem}
  .display-banner-sub{color:#8AAFCC;font-size:.82rem;margin-top:2px}
  .stTabs [data-baseweb="tab-list"]{background:rgba(255,255,255,.05);border-radius:10px;
    padding:4px;gap:6px}
  .stTabs [data-baseweb="tab"]{color:#8AAFCC;border-radius:8px;font-size:1rem;padding:8px 20px}
  .stTabs [aria-selected="true"]{background:rgba(41,181,232,.18)!important;
    color:#FFFFFF!important;font-weight:600}
  .panel{background:rgba(255,255,255,.04);border:1px solid rgba(41,181,232,.2);
    border-radius:14px;padding:22px;margin-bottom:16px}
  .sec-label{color:#F5A623;font-weight:700;font-size:.85rem;letter-spacing:.08em;
    text-transform:uppercase;border-bottom:1px solid rgba(245,166,35,.25);
    padding-bottom:6px;margin-bottom:14px}
  .total-bubble{background:linear-gradient(135deg,#29B5E8 0%,#1B3A6A 100%);
    border-radius:16px;text-align:center;padding:22px 10px 18px}
  .total-num{font-size:3.2rem;font-weight:900;color:#FFFFFF;line-height:1}
  .total-lbl{color:rgba(255,255,255,.7);font-size:.85rem;margin-top:6px}
  .style-tag{display:inline-block;background:rgba(245,166,35,.15);border:1px solid #F5A623;
    color:#F5A623;border-radius:30px;font-size:.9rem;font-weight:600;padding:5px 16px;margin-bottom:14px}
  .bonus-badge{background:#F5A623;color:#0D1B2A;border-radius:20px;font-size:.75rem;
    font-weight:700;padding:2px 10px;display:inline-block;margin-left:8px}
  .ai-comment{background:rgba(41,181,232,.08);border-left:4px solid #29B5E8;
    border-radius:0 10px 10px 0;padding:14px 18px;color:#CFE9F6;
    font-style:italic;font-size:.93rem;line-height:1.6}
  .steps-box{background:linear-gradient(135deg,#1B3253,#0D1B2A);border:3px solid #F5A623;
    border-radius:20px;text-align:center;padding:30px 20px}
  .steps-num{font-size:3.5rem;font-weight:900;color:#F5A623;letter-spacing:2px;line-height:1}
  .steps-lbl{color:#8AAFCC;font-size:.95rem;margin-top:8px}
  .conf-high{color:#48BB78;font-size:.8rem}
  .conf-medium{color:#ECC94B;font-size:.8rem}
  .conf-low{color:#FC8181;font-size:.8rem}
  .lb-row{display:flex;align-items:center;background:rgba(255,255,255,.04);
    border:1px solid rgba(255,255,255,.07);border-radius:10px;padding:12px 16px;margin:6px 0}
  .lb-rank{font-size:1.4rem;min-width:42px}
  .lb-name{flex:1;font-weight:600;color:#FFFFFF;font-size:.97rem}
  .lb-score{color:#F5A623;font-weight:700;font-size:1.1rem;min-width:70px;text-align:right}
  .lb-time{color:#8AAFCC;font-size:.78rem;margin-left:14px}
  div[data-testid="stButton"]>button{background:linear-gradient(90deg,#29B5E8,#1A79C0)!important;
    color:#FFFFFF!important;border:none!important;border-radius:8px!important;
    font-weight:700!important;padding:10px 28px!important;width:100%!important;font-size:1rem!important}
  div[data-testid="stButton"]>button:hover{background:linear-gradient(90deg,#1A79C0,#0F5A99)!important}
  div[data-testid="stButton"]>button:disabled{background:rgba(255,255,255,.1)!important;
    color:rgba(255,255,255,.3)!important}
  .stTextInput>div>input,.stNumberInput>div>input{background:rgba(255,255,255,.07)!important;
    border:1px solid rgba(41,181,232,.35)!important;color:#FFFFFF!important;border-radius:8px!important}
  label{color:#CBD5E0!important}
  [data-testid="stFileUploader"]{background:rgba(255,255,255,.03);
    border:2px dashed rgba(41,181,232,.35)!important;border-radius:12px!important}
  hr{border-color:rgba(255,255,255,.08)!important}
</style>
""", unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🏆 Snowflake Korea Internal Awards 2026</h1>
  <p>Snowflake World Tour Seoul · Powered by Snowflake Cortex ✨ · 파일명 = 이름 자동 인식</p>
</div>
""", unsafe_allow_html=True)

if not SNOWFLAKE_AVAILABLE:
    st.warning("⚠️ Snowflake 세션에 연결되어 있지 않습니다.")

# ── 전광판 + 관리자 배너 ─────────────────────────────────────
b_left, b_mid, b_right = st.columns([4, 1, 1])
with b_left:
    st.markdown(
        '<div class="display-banner">'
        '<div><div class="display-banner-text">🖥️ 발표용 전광판 모드</div>'
        '<div class="display-banner-sub">실시간 리더보드 슬라이드쇼 · 10초 자동 전환</div></div>'
        '</div>', unsafe_allow_html=True)
with b_mid:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🖥️ 전광판 시작", key="enter_display"):
        st.query_params["mode"]  = "display"
        st.query_params["slide"] = "0"
        st.rerun()
with b_right:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🔐 관리자", key="enter_admin"):
        st.query_params["mode"] = "admin"
        st.rerun()

# ══════════════════════════════════════════════════════════════
#  TABS
# ══════════════════════════════════════════════════════════════
tab_dress, tab_steps = st.tabs(["👗  AI 베스트 드레서", "🦶  맨발에 땀나 상"])

# ─────────────────────────────────────────────────────────────
#  TAB 1 — AI 베스트 드레서
# ─────────────────────────────────────────────────────────────
with tab_dress:
    col_left, col_right = st.columns([1, 1.15], gap="large")
    with col_left:
        st.markdown('<div class="panel"><div class="sec-label">📸 사진 제출</div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#8AAFCC;font-size:.85rem;margin-bottom:12px;line-height:1.6">'
                    '💡 <strong style="color:#29B5E8">파일명을 본인 이름으로 저장</strong>해서 업로드하세요<br>'
                    '&nbsp;&nbsp; 예) <code>hailey_jung.jpg</code> → <strong>Hailey Jung</strong>'
                    '</div>', unsafe_allow_html=True)
        d_file = st.file_uploader("스타일 사진 (얼굴 제외)", type=["jpg","jpeg","png","webp"], key="d_file")
        d_name = ""
        if d_file:
            d_name = extract_name_from_filename(d_file.name)
            st.markdown(name_chip_html(d_name, d_file.name), unsafe_allow_html=True)
            with st.expander("✏️ 이름 수정하기", expanded=False):
                ov = st.text_input("이름 직접 입력", value=d_name, key="d_name_ov",
                                   label_visibility="collapsed")
                if ov.strip(): d_name = ov.strip()
            st.image(d_file, caption=f"업로드: {d_file.name}", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.markdown('<div class="panel"><div class="sec-label">📋 채점 기준</div>', unsafe_allow_html=True)
        for _, label, pts in CATEGORIES:
            st.markdown(f'<div style="display:flex;justify-content:space-between;margin:4px 0">'
                        f'<span style="color:#CBD5E0;font-size:.88rem">{label}</span>'
                        f'<span style="color:#8AAFCC;font-weight:700">{pts}점</span></div>',
                        unsafe_allow_html=True)
        st.markdown('<div style="color:#F5A623;font-size:.82rem;margin-top:10px">'
                    '🎁 Snowflake 굿즈 착용 시 +2점!</div></div>', unsafe_allow_html=True)

        analyze_btn = st.button("🤖 AI 분석 시작", key="analyze_btn",
                                disabled=(not d_file or not d_name))

    if analyze_btn:
        if not SNOWFLAKE_AVAILABLE:
            st.error("Snowflake Cortex를 사용할 수 없습니다.")
        else:
            d_file.seek(0)
            with st.spinner(f"✨ {d_name} 님의 스타일을 분석 중..."):
                try:
                    img_bytes = prepare_image(d_file)
                    result    = analyze_fashion(img_bytes)
                    st.session_state.dress_result    = result
                    st.session_state.dress_name      = d_name
                    st.session_state.dress_thumb     = make_thumb(img_bytes)
                    st.session_state.dress_submitted = False
                except Exception as e:
                    st.error(f"분석 오류: {e}")

    with col_right:
        result = st.session_state.get("dress_result")
        if result:
            scores   = result.get("scores",{})
            comments = result.get("comments",{})
            bonus    = result.get("bonus", False)
            total    = sum(scores.values()) + (BONUS_PTS if bonus else 0)
            title    = result.get("style_title","")
            comment  = result.get("overall_comment","")
            rname    = st.session_state.get("dress_name","")

            if title: st.markdown(f'<div class="style-tag">✨ {title}</div>', unsafe_allow_html=True)
            if bonus: st.markdown('<span class="bonus-badge">🎁 +2점</span>', unsafe_allow_html=True)

            sc_col, tot_col = st.columns([1.6,1], gap="medium")
            with sc_col:
                st.markdown('<div class="panel"><div class="sec-label">항목별 점수</div>', unsafe_allow_html=True)
                for key, label, max_pts in CATEGORIES:
                    st.markdown(score_bar_html(label, scores.get(key,0), max_pts,
                                               comments.get(key,"")), unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            with tot_col:
                st.markdown(f'<div class="total-bubble"><div class="total-num">{total}</div>'
                            f'<div class="total-lbl">총점 / {MAX_BASE+BONUS_PTS}</div></div>',
                            unsafe_allow_html=True)
            if comment:
                st.markdown(f'<div class="ai-comment">🤖 {comment}</div>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            if st.session_state.get("dress_submitted"):
                st.success(f"✅ **{rname}** 님의 점수가 리더보드에 등록됐습니다!")
            else:
                if st.button("🏆 리더보드에 등록", key="submit_dress"):
                    save_dresser(rname, result,
                                 thumb_bytes=st.session_state.get("dress_thumb"))
                    st.session_state.dress_submitted = True
                    st.rerun()
        else:
            st.markdown('<div class="panel" style="text-align:center;padding:60px 20px;color:#8AAFCC">'
                        '<div style="font-size:3rem">👗</div>'
                        '<div style="margin-top:12px">이름이 담긴 파일명으로 사진을 업로드하고<br>'
                        '<strong style="color:#29B5E8">AI 분석 시작</strong> 버튼을 눌러주세요</div></div>',
                        unsafe_allow_html=True)

    st.markdown("<br>"); st.markdown("---")
    st.markdown('<div class="sec-label" style="font-size:1rem;margin-bottom:18px">'
                '🏆 베스트 드레서 리더보드</div>', unsafe_allow_html=True)
    lb_c1, lb_c2 = st.columns([2,1], gap="large")
    with lb_c1:
        lb_data = load_dresser_lb()
        if not lb_data:
            st.info("아직 제출된 점수가 없습니다. 첫 번째 주인공이 되어보세요! 🎉")
        else:
            for i, row in enumerate(lb_data):
                bh = '<span class="bonus-badge">굿즈 +2</span>' if row.get("bonus") else ""
                th = (f'<div style="color:#8AAFCC;font-size:.78rem;margin-top:2px">'
                      f'{row["style_title"]}</div>') if row.get("style_title") else ""
                st.markdown(f'<div class="lb-row">'
                            f'<span class="lb-rank">{rank_emoji(i)}</span>'
                            f'<span class="lb-name">&nbsp;{row["name"]}{bh}{th}</span>'
                            f'<span class="lb-score">{row["total_score"]}점</span>'
                            f'<span class="lb-time">{row.get("submitted_at","")}</span></div>',
                            unsafe_allow_html=True)
    with lb_c2:
        if lb_data:
            df = pd.DataFrame([{"이름":r["name"],"색상":r.get("color_score",0),
                                 "스타일":r.get("styling_score",0),"액세서리":r.get("accessories_score",0),
                                 "적합성":r.get("approp_score",0),"창의성":r.get("creativity_score",0),
                                 "합계":r.get("total_score",0)} for r in lb_data[:5]])
            st.dataframe(df, hide_index=True, use_container_width=True,
                         column_config={"합계": st.column_config.ProgressColumn(
                             "합계", min_value=0, max_value=MAX_BASE+BONUS_PTS, format="%d")})


# ─────────────────────────────────────────────────────────────
#  TAB 2 — 맨발에 땀나 상
# ─────────────────────────────────────────────────────────────
with tab_steps:
    col_s_left, col_s_right = st.columns([1, 1.15], gap="large")
    with col_s_left:
        st.markdown('<div class="panel"><div class="sec-label">📱 만보기 스크린샷 제출</div>', unsafe_allow_html=True)
        st.markdown('<div style="color:#8AAFCC;font-size:.85rem;margin-bottom:12px;line-height:1.6">'
                    '💡 <strong style="color:#29B5E8">파일명을 본인 이름으로 저장</strong>해서 업로드하세요<br>'
                    '&nbsp;&nbsp; 예) <code>james_park.png</code> → <strong>James Park</strong>'
                    '</div>', unsafe_allow_html=True)
        s_file = st.file_uploader("만보기 스크린샷", type=["jpg","jpeg","png","webp"], key="s_file")
        s_name = ""
        if s_file:
            s_name = extract_name_from_filename(s_file.name)
            st.markdown(name_chip_html(s_name, s_file.name), unsafe_allow_html=True)
            with st.expander("✏️ 이름 수정하기", expanded=False):
                ov2 = st.text_input("이름 직접 입력", value=s_name, key="s_name_ov",
                                    label_visibility="collapsed")
                if ov2.strip(): s_name = ov2.strip()
            st.image(s_file, caption=f"업로드: {s_file.name}", use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown('<div class="panel" style="font-size:.88rem;color:#8AAFCC;line-height:1.7">'
                    '<div class="sec-label">📋 참여 방법</div>'
                    '1️⃣ 파일명을 <strong style="color:#FFFFFF">본인 이름</strong>으로 저장<br>'
                    '2️⃣ 걸음 수 스크린샷 촬영 후 업로드<br>'
                    '3️⃣ AI가 자동으로 걸음 수를 읽어드립니다<br>'
                    '4️⃣ 숫자 확인 후 리더보드에 제출!<br><br>'
                    '<span style="color:#F5A623">⚠️ 공동 1위 시 먼저 제출한 순서 결정 😄</span>'
                    '</div>', unsafe_allow_html=True)
        read_btn = st.button("👟 걸음 수 읽기", key="read_steps_btn",
                             disabled=(not s_file or not s_name))

    if read_btn:
        if not SNOWFLAKE_AVAILABLE:
            st.error("Snowflake Cortex를 사용할 수 없습니다.")
        else:
            s_file.seek(0)
            with st.spinner(f"🔍 {s_name} 님의 걸음 수를 AI가 읽는 중..."):
                try:
                    img_bytes = prepare_image(s_file)
                    result    = extract_steps(img_bytes)
                    st.session_state.steps_result    = result
                    st.session_state.steps_name      = s_name
                    st.session_state.steps_thumb     = make_thumb(img_bytes)
                    st.session_state.steps_submitted = False
                except Exception as e:
                    st.error(f"분석 오류: {e}")

    with col_s_right:
        sres = st.session_state.get("steps_result")
        if sres:
            steps    = sres.get("steps",0)
            conf     = sres.get("confidence","low")
            note     = sres.get("note","")
            ccls     = {"high":"conf-high","medium":"conf-medium"}.get(conf,"conf-low")
            ctxt     = {"high":"✅ 높음","medium":"⚠️ 보통","low":"❓ 낮음"}.get(conf,"")
            sname    = st.session_state.get("steps_name","")
            st.markdown(f'<div class="steps-box"><div class="steps-num">{steps:,}</div>'
                        f'<div class="steps-lbl">👣 {sname} 님의 오늘 걸음 수</div>'
                        f'<div class="{ccls}" style="margin-top:10px">인식 신뢰도: {ctxt}</div></div>',
                        unsafe_allow_html=True)
            if note:
                st.markdown(f'<div style="color:#8AAFCC;font-size:.85rem;margin-top:10px;'
                            f'font-style:italic;text-align:center">{note}</div>', unsafe_allow_html=True)
            st.markdown("<br>")
            st.markdown('<div class="panel"><div class="sec-label">✏️ 숫자가 다른가요?</div>',
                        unsafe_allow_html=True)
            edited = st.number_input("걸음 수 확인/수정", value=int(steps),
                                      min_value=0, max_value=100000, step=1, key="steps_edit")
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("<br>")
            if st.session_state.get("steps_submitted"):
                st.success(f"✅ **{sname}** 님의 걸음 수가 등록됐습니다!")
            else:
                if st.button("🏆 리더보드에 등록", key="submit_steps"):
                    save_steps(sname, int(edited),
                               thumb_bytes=st.session_state.get("steps_thumb"))
                    st.session_state.steps_submitted = True
                    st.rerun()
        else:
            st.markdown('<div class="panel" style="text-align:center;padding:60px 20px;color:#8AAFCC">'
                        '<div style="font-size:3rem">🦶</div>'
                        '<div style="margin-top:12px">이름이 담긴 파일명으로 스크린샷을 업로드하고<br>'
                        '<strong style="color:#29B5E8">걸음 수 읽기</strong> 버튼을 눌러주세요</div></div>',
                        unsafe_allow_html=True)

    st.markdown("<br>"); st.markdown("---")
    st.markdown('<div class="sec-label" style="font-size:1rem;margin-bottom:18px">'
                '🦶 만보기 리더보드</div>', unsafe_allow_html=True)
    slb_data = load_steps_lb()
    if not slb_data:
        st.info("아직 제출된 기록이 없습니다. 첫 번째 기록을 세워보세요! 🎉")
    else:
        s_c1, s_c2 = st.columns([1.4,1], gap="large")
        mx = max(r["steps"] for r in slb_data)
        with s_c1:
            for i, row in enumerate(slb_data):
                pct = min(int(row["steps"]/mx*100),100) if mx else 0
                st.markdown(f'<div class="lb-row">'
                            f'<span class="lb-rank">{rank_emoji(i)}</span>'
                            f'<span class="lb-name">&nbsp;{row["name"]}{"  👑" if i==0 else ""}</span>'
                            f'<span class="lb-score">{row["steps"]:,} 걸음</span>'
                            f'<span class="lb-time">{row.get("submitted_at","")}</span></div>'
                            f'<div style="background:rgba(255,255,255,.06);border-radius:4px;'
                            f'height:4px;margin:-3px 0 4px 42px">'
                            f'<div style="background:#F5A623;width:{pct}%;height:100%;border-radius:4px">'
                            f'</div></div>', unsafe_allow_html=True)
        with s_c2:
            df_s = pd.DataFrame([{"이름":r["name"],"걸음 수":r["steps"],
                                   "등록":r.get("submitted_at","")} for r in slb_data])
            st.dataframe(df_s, hide_index=True, use_container_width=True,
                         column_config={"걸음 수": st.column_config.ProgressColumn(
                             "걸음 수", min_value=0, max_value=mx, format="%d")})

# ── Footer ────────────────────────────────────────────────────
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown(
    '<div style="text-align:center;color:rgba(138,175,204,.5);font-size:.8rem;letter-spacing:.05em">'
    'CREATED WITH <a href="https://ai.snowflake.com" style="color:rgba(138,175,204,.7);'
    'text-decoration:none;font-weight:600">SNOWFLAKE COWORK</a>'
    ' &nbsp;·&nbsp; Snowflake Korea Internal Awards 2026'
    ' &nbsp;·&nbsp; <a href="?mode=admin" style="color:rgba(138,175,204,.4);text-decoration:none">'
    '관리자</a></div>', unsafe_allow_html=True)
