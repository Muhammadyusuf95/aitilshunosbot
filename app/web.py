"""Veb qism: sog'liq tekshiruvi va Telegram Mini-App (jonli reyting). initData server tomonida tekshiriladi."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

from flask import Flask, jsonify, render_template_string, request

from app import config, levels
from app.db import get_db

app = Flask(__name__)


def validate_init_data(init_data, token, max_age=86400):
    """Telegram WebApp initData imzosini tekshiradi. To'g'ri bo'lsa user dict, aks holda None."""
    if not init_data or not token:
        return None
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = pairs.pop("hash", None)
        if not recv_hash:
            return None
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            return None
        if time.time() - int(pairs.get("auth_date", 0)) > max_age:
            return None
        return json.loads(pairs.get("user", "{}"))
    except Exception:  # noqa: BLE001
        return None


def board(period, limit=50):
    rows = get_db().leaderboard(period, limit)
    out = []
    for i, r in enumerate(rows, 1):
        total = int(r["total"] or 0)
        correct = int(r["correct"] or 0)
        lv = levels.level_for(int(r.get("points") or 0))[0]
        out.append(dict(
            rank=i, uid=r["user_id"], name=r["name"] or "Ishtirokchi", correct=correct, total=total,
            acc=round(100 * correct / total) if total else 0, tests=int(r["tests"] or 0),
            streak=int(r.get("streak") or 0), level=f"{lv[2]} {lv[1]}",
        ))
    return out


@app.route("/")
def home():
    return "AI Tilshunos ishlayapti ✅", 200


@app.route("/health")
def health():
    return jsonify(status="ok", version=config.BOT_VERSION)


@app.route("/api/leaderboard")
def api_leaderboard():
    period = request.args.get("period", "week")
    if period not in ("week", "month", "all"):
        period = "week"
    rows = board(period)
    me = validate_init_data(request.args.get("initData", ""), config.TELEGRAM_TOKEN)
    my_rank = None
    if me and me.get("id"):
        full = board(period, 5000)
        mine = next((r for r in full if r["uid"] == me["id"]), None)
        my_rank = dict(mine, uid=None) if mine else None
    for r in rows:
        r.pop("uid", None)  # Telegram ID ommaga ko'rsatilmaydi
    return jsonify(period=period, rows=rows, me=my_rank)


@app.route("/leaderboard")
def leaderboard_page():
    return render_template_string(PAGE, channel=config.CHANNEL_URL, bot=config.BOT_USERNAME)


PAGE = r"""<!doctype html>
<html lang="uz"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>Reyting · AI Tilshunos</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<style>
:root{--bg:var(--tg-theme-bg-color,#0f1220);--fg:var(--tg-theme-text-color,#eef0ff);--hint:var(--tg-theme-hint-color,#8d93b5);
--card:var(--tg-theme-secondary-bg-color,#181c31);--accent:var(--tg-theme-button-color,#6c7bff);--gold:#f5b942;--silver:#b8c0d4;--bronze:#d58a54}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--fg);font:15px/1.4 -apple-system,"Segoe UI",Roboto,sans-serif;padding:16px 14px 40px}
h1{font-size:20px;font-weight:700}.sub{color:var(--hint);font-size:13px;margin:2px 0 14px}
.tabs{display:flex;gap:6px;background:var(--card);padding:4px;border-radius:12px;margin-bottom:16px}
.tab{flex:1;text-align:center;padding:8px 0;border-radius:9px;font-size:13px;font-weight:600;color:var(--hint);cursor:pointer;border:0;background:none}
.tab.on{background:var(--accent);color:#fff}
.podium{display:grid;grid-template-columns:1fr 1.15fr 1fr;gap:8px;align-items:end;margin-bottom:16px}
.pod{background:var(--card);border-radius:14px;padding:12px 6px;text-align:center}
.pod .m{font-size:26px}.pod .n{font-weight:700;font-size:13px;margin:4px 0 2px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.pod .s{font-size:12px;color:var(--hint)}.pod.p1{padding-top:20px;border:1px solid var(--gold)}
.row{display:flex;align-items:center;gap:10px;background:var(--card);padding:10px 12px;border-radius:12px;margin-bottom:6px}
.row.me{outline:2px solid var(--accent)}.rk{width:26px;text-align:center;font-weight:700;color:var(--hint)}
.nm{flex:1;min-width:0}.nm b{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.nm small{color:var(--hint);font-size:12px}.sc{text-align:right}.sc b{font-size:17px}.sc small{display:block;color:var(--hint);font-size:11px}
.empty{text-align:center;color:var(--hint);padding:40px 0}
.me-card{background:linear-gradient(135deg,var(--accent),#8b5cf6);color:#fff;border-radius:14px;padding:12px 14px;margin-bottom:14px;display:none}
.foot{text-align:center;margin-top:18px}.foot a{color:var(--accent);text-decoration:none;font-size:13px}
</style></head><body>
<h1>🏆 Bilimdonlar reytingi</h1><div class="sub">To'g'ri javoblar soni bo'yicha · tezlik tie-break</div>
<div class="me-card" id="me"></div>
<div class="tabs"><button class="tab on" data-p="week">Hafta</button><button class="tab" data-p="month">Oy</button><button class="tab" data-p="all">Hamma vaqt</button></div>
<div id="podium" class="podium"></div><div id="list"></div>
<div class="foot"><a href="{{channel}}">📢 Kanalimiz</a></div>
<script>
const tg=window.Telegram&&Telegram.WebApp;if(tg){tg.ready();tg.expand();}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const medal=['🥇','🥈','🥉'];
async function load(p){
  const q=new URLSearchParams({period:p,initData:tg?tg.initData:''});
  let d;try{d=await (await fetch('/api/leaderboard?'+q)).json();}catch(e){document.getElementById('list').innerHTML='<div class="empty">Yuklab bo\'lmadi</div>';return;}
  const rows=d.rows||[];
  const me=document.getElementById('me');
  if(d.me){me.style.display='block';me.innerHTML='Sizning o\'rningiz: <b>#'+d.me.rank+'</b> · '+d.me.correct+' to\'g\'ri · '+d.me.acc+'% · '+esc(d.me.level);}else{me.style.display='none';}
  if(!rows.length){document.getElementById('podium').innerHTML='';document.getElementById('list').innerHTML='<div class="empty">Hozircha natijalar yo\'q.<br>Birinchi bo\'ling! 🚀</div>';return;}
  const order=[rows[1],rows[0],rows[2]];
  document.getElementById('podium').innerHTML=order.map((r,i)=>r?'<div class="pod '+(i==1?'p1':'')+'"><div class="m">'+medal[r.rank-1]+'</div><div class="n">'+esc(r.name)+'</div><div class="s">'+r.correct+' ✓ · '+r.acc+'%</div></div>':'<div></div>').join('');
  document.getElementById('list').innerHTML=rows.slice(3).map(r=>'<div class="row'+(d.me&&d.me.rank==r.rank?' me':'')+'"><div class="rk">'+r.rank+'</div><div class="nm"><b>'+esc(r.name)+'</b><small>'+esc(r.level)+' · 🔥'+r.streak+' · '+r.tests+' test</small></div><div class="sc"><b>'+r.correct+'</b><small>'+r.acc+'%</small></div></div>').join('');
}
document.querySelectorAll('.tab').forEach(t=>t.onclick=()=>{document.querySelectorAll('.tab').forEach(x=>x.classList.remove('on'));t.classList.add('on');load(t.dataset.p);});
load('week');
</script></body></html>"""


def run_web():
    app.run(host="0.0.0.0", port=config.PORT, debug=False, use_reloader=False)
