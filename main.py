import os
import threading
import json
import random
import time
from datetime import datetime, timedelta
import pytz
import requests
from flask import Flask, render_template_string
import telebot
from telebot import types as tele_types
from google import genai
from google.genai import types

# --- RENDER WEB SERVICE VA TELEGRAM WEBAPP SERVERI ---
app = Flask(__name__)
RESULTS_FILE = "test_results.json"
USERS_FILE = "users.json"
COUNTERS_FILE = "quiz_counters.json"

def load_data(filepath):
    if not os.path.exists(filepath):
        return {}
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_data(filepath, data):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

WEBAPP_HTML = """
<!DOCTYPE html>
<html lang="uz">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no">
  <title>BMB Test Reytingi & Shaxsiy Kabinet</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root {
      --bg: #0f172a;
      --card: #1e293b;
      --primary: #38bdf8;
      --accent: #f59e0b;
      --text: #f8fafc;
      --text-dim: #94a3b8;
    }
    body {
      margin: 0;
      padding: 16px;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: var(--bg);
      color: var(--text);
    }
    .header {
      text-align: center;
      margin-bottom: 20px;
    }
    .badge {
      display: inline-block;
      padding: 4px 12px;
      background: rgba(56, 189, 248, 0.15);
      color: var(--primary);
      border-radius: 999px;
      font-size: 12px;
      font-weight: 600;
      margin-bottom: 8px;
    }
    h1 {
      font-size: 20px;
      margin: 0 0 6px 0;
    }
    .sub {
      color: var(--text-dim);
      font-size: 13px;
    }
    .stats-grid {
      display: grid;
      grid-template-columns: 1fr 1fr 1fr;
      gap: 8px;
      margin-bottom: 18px;
    }
    .stat-card {
      background: var(--card);
      padding: 12px 6px;
      border-radius: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05);
      text-align: center;
    }
    .stat-val {
      font-size: 16px;
      font-weight: bold;
      color: var(--primary);
    }
    .stat-lbl {
      font-size: 10px;
      color: var(--text-dim);
      margin-top: 2px;
    }
    .leaderboard {
      background: var(--card);
      border-radius: 16px;
      padding: 12px;
      border: 1px solid rgba(255, 255, 255, 0.05);
    }
    .row {
      display: flex;
      align-items: center;
      padding: 10px 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .row:last-child {
      border-bottom: none;
    }
    .rank {
      width: 28px;
      font-weight: 700;
      font-size: 14px;
    }
    .rank-1 { color: #fbbf24; }
    .rank-2 { color: #94a3b8; }
    .rank-3 { color: #d97706; }
    .info {
      flex: 1;
      padding: 0 8px;
    }
    .name {
      font-size: 14px;
      font-weight: 600;
    }
    .details {
      font-size: 11px;
      color: var(--text-dim);
    }
    .score {
      font-weight: 700;
      color: var(--primary);
      font-size: 13px;
      text-align: right;
    }
  </style>
</head>
<body>
  <div class="header">
    <div class="badge">MILLIY SERTIFIKAT & BMB</div>
    <h1>🏆 Jonli Reyting & Darajalar</h1>
    <div class="sub">@onatilidanyordam hamjamiyati</div>
  </div>

  <div class="stats-grid">
    <div class="stat-card">
      <div class="stat-val">{{ total_users }}</div>
      <div class="stat-lbl">A'zolar</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">{{ total_tested }}</div>
      <div class="stat-lbl">Test topshirganlar</div>
    </div>
    <div class="stat-card">
      <div class="stat-val">{{ active_streaks }}</div>
      <div class="stat-lbl">🔥 Faol seriyalar</div>
    </div>
  </div>

  <div class="leaderboard">
    {% for user in top_users %}
    <div class="row">
      <div class="rank rank-{{ user.rank }}">{{ user.rank_icon }}</div>
      <div class="info">
        <div class="name">{{ user.name }}</div>
        <div class="details">🔥 {{ user.streak }} kun seriya • {{ user.points }} ball</div>
      </div>
      <div class="score">
        {{ user.correct }}/30 to'g'ri<br>
        <span style="font-size:10px; color:var(--text-dim); font-weight:normal;">⏳ {{ user.duration_str }}</span>
      </div>
    </div>
    {% else %}
    <div style="text-align: center; padding: 20px; color: var(--text-dim); font-size: 13px;">
      Hozircha natijalar mavjud emas. Birinchi bo'lib test topshiring!
    </div>
    {% endfor %}
  </div>

  <script>
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.ready();
      window.Telegram.WebApp.expand();
    }
  </script>
</body>
</html>
"""

@app.route('/')
def home():
    return "AI Tilshunos & Metodist v11.0 (Milliy Sertifikat Suite) Faol!"

@app.route('/leaderboard')
def webapp_leaderboard():
    results = load_data(RESULTS_FILE)
    users = load_data(USERS_FILE)
    
    sorted_res = sorted(
        results.items(), 
        key=lambda x: (
            -x[1].get("correct", 0), 
            -users.get(str(x[0]), {}).get("points", 0),
            x[1].get("duration", 999999)
        )
    )[:25]
    
    top_list = []
    active_streak_count = sum(1 for _, u in users.items() if u.get("streak", 0) > 1)

    for idx, (uid, info) in enumerate(sorted_res, 1):
        icon = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"#{idx}"
        dur = info.get("duration", 0)
        dur_str = f"{dur//60}m {dur%60}s"
        u_record = users.get(str(uid), {})
        
        top_list.append({
            "rank": idx,
            "rank_icon": icon,
            "name": info.get("name", "Ishtirokchi"),
            "correct": info.get("correct", 0),
            "duration_str": dur_str,
            "streak": u_record.get("streak", 1),
            "points": u_record.get("points", 0)
        })

    return render_template_string(
        WEBAPP_HTML,
        total_users=len(users),
        total_tested=len(results),
        active_streaks=active_streak_count,
        top_users=top_list
    )

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

RENDER_APP_URL = "https://aitilshunosbot.onrender.com"

def keep_alive():
    while True:
        try:
            time.sleep(600)
            requests.get(RENDER_APP_URL)
        except Exception:
            pass

threading.Thread(target=keep_alive, daemon=True).start()

TELEGRAM_TOKEN = "8753873278:AAHtYTR7bduo4cFEbfTz0f9g_cUKBsWk04I"
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

CHANNEL_USERNAME = "@onatilidanyordam"
ADMIN_ID = 5423849679

bot = telebot.TeleBot(TELEGRAM_TOKEN)
ai_client = genai.Client(api_key=GEMINI_API_KEY)

ACTIVE_QUIZ_TRACKER = {}
POLL_CORRECT_MAP = {}
READY_MATCHES = {}
ADMIN_POST_STORAGE = {}
PENDING_QUIZZES = {}

BANNER_IMAGES = {
    "talaba": "https://images.unsplash.com/photo-1457369804613-52c61a468e7d?w=900&auto=format&fit=crop&q=80",
    "oqituvchi": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655?w=900&auto=format&fit=crop&q=80",
    "abituriyent": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=900&auto=format&fit=crop&q=80",
    "izlanuvchi": "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=900&auto=format&fit=crop&q=80",
    "milliy_sertifikat": "https://images.unsplash.com/photo-1455390582262-044cdead277a?w=900&auto=format&fit=crop&q=80"
}

IMZO = (
    "\n\n╭───────────────────────╮\n"
    f"  🏛 **Rasmiy kanal:** {CHANNEL_USERNAME}\n"
    "  ✨ **AI Asistent:** @aitilshunosbot\n"
    "╰───────────────────────╯"
)

# --- 19 TA RASMIY IMTIHON ESSE MAVZULARI ---
OFFICIAL_ESSAY_TOPICS = [
    "Aksariyat maktab bitiruvchilari oliy ta'limni talab etmaydigan zamonaviy kasblarni egallashga qiziqish bildirishsa, ayrimlar zamonaviy kasblar insonga butun umrlik faoliyat bo'lib qolishiga ishonishmaydi.",
    "Ba'zilar bolaga mukammal bilim berish uchun uni xususiy maktabda o'qitish kerak deb hisoblashsa, ayrimlar davlat maktabida ham mukammal bilim olish mumkin deb bilishadi.",
    "Ayrimlar turli shoular va yutuqli oʻyinlar odamlarning bir-biriga bo'lgan ishonchini soʻndiradi degan fikrda, ba'zilar esa bunday ko'ngilochar oʻyinlarning afzalliklari haqida gapirishadi.",
    "Ayrimlar chet tilini o'rganish madaniylikning bir belgisi deb bilsalar, ba'zilar o'zga tilini bilish moddiy hayotni ta'minlaydi deydilar.",
    "Hozirgi kunda ayrim insonlar reklamalarga ma'lumot ulashishning eng samarali usuli deb qarasa, ayrimlar bu borada cheklovlar qo'yish kerak deb bilishadi.",
    "Ayrimlar ko'p farzandlilik davlat va jamiyat taraqqiyoti uchun foyda keltiradi deb bilsa, ayrimlar oilada farzand tarbiyasiga e'tibor yetarli bo'lmaydi deb hisoblashadi.",
    "Ko'p qavatli uylar qurilishining avj olishi shahar arxitekturasi va dizayniga yangicha tus beradi, biroq koʻp aholi bunday uylar o'rniga xonadon yoki manzarali yer maydoni qurilishini ma'qul topadi.",
    "Ba'zilar kredit yillar davomida ushalmagan orzularni amalga oshirishning qulay yo'li deb hisoblashadi, ayrimlari esa kredit ortiqcha xarajat va moliyaviy holatni qiyinlashtiradi degan fikrda.",
    "Bugungi kunda sodir bo'layotgan jinoyatlar OAV, internet tarmoqlari orqali ommaga taqdim etilmoqda. Baʼzilarning fikricha, jinoyatlarning bunday oshkora ko'rsatilishi jinoyatga yo'l ochib berishi mumkin, baʼzilar esa ochiq ko'rsatish tarafdori.",
    "Ayrimlar oilaviy muammolar aks etgan videolavhalarning ijtimoiy tarmoqlarda tarqalishi jamiyat ma'naviyatiga va ruhiyatiga salbiy ta'sir koʻrsatadi deb bilishsa, ayrimlar aksincha fikrda.",
    "Ayrimlar yaxshi yashash uchun bitta kasbning mohir ustasi bo'lish kerak deb bilishsa, ba'zilar bir necha kasbning egasi bo'lish foydaliroq deb hisoblashadi.",
    "Sun'iy intellektning insoniyat hayotiga ijobiy va salbiy tomonlari.",
    "Plastik qadoqdagi suv iste'moli afzalmi yoki vodoprovod suvi?",
    "O'qitishda milliy usullarni yanada rivojlantirish muhimmi yoki chet el tajribasini qo'llashmi?",
    "Anʼanaviy to'ylar xorijiy to'ylar kabi ixcham va zamonaviy tarzda o'tkazilishiga qanday qaraysiz?",
    "Zamonaviy kitobxonlar audio kitoblarning afzalligini ta'kidlashmoqda, ammo ba'zilar bu fikrga qarshi.",
    "Psixologlar tarbiyada erkinlik muhimligini taʼkidlashmoqda, ammo ba'zilar erkinlik salbiy oqibatlarga olib keladi degan fikrda.",
    "Ba'zilar inson faoliyati tufayli yer shari zararlanib borayotganini ta'kidlashmoqda, ayrimlar esa inson faoliyati uni yashash uchun yaxshiroq joyga aylantiradi deb o'ylaydi.",
    "Ba'zilar ta'lim olish jarayonida mehnat faoliyati bilan ham shug'ullansa tajriba oshadi deyishadi, ayrimlari esa ta'lim jarayonida chalg'imasdan faqat bilim olish muhimligini ta'kidlashadi."
]

# --- 21 TA 50 BALLIK NAMUNAVIY ESSELAR BAZASI ---
SAMPLE_ESSAYS_BANK = [
    {
        "title": "1. Diplom talab etmaydigan zamonaviy kasblar",
        "text": "Dunyo rivojlangani sari zamonaviy kasblar ham takomillashib bormoqda. Katta hayot ostonasiga qadam qoʻyayotgan ko'plab o'quvchilar hozirgi kunda diplom talab qilmaydigan kasblarni oʻzlashtirishga xohish bildirishmoqda. Ammo baʼzilar bunday kasblarning kelajagi mavhum, inson uchun butun umrlik faoliyat bo'la olmaydi deb hisoblashmoqda. Quyidagi esseda har ikkala qarashni ko'rib chiqamiz.\n\nBirinchi qarash tarafdorlarining fikriga ko'ra, innovatsion kasblar qisqa muddatda o'rganiladi va yaxshi daromad keltiradi. Yangi avlod kasblariga IT, dizayn, marketing, treyding, servis sohalari kiradi. Ularning afzalliklari, birinchidan, oliy ta'limni talab etmasligi, ikkinchidan, qisqa muddatli kurslar orqali oʻrganish mumkinligidadir. Atrofimizga nazar tashlaydigan bo'lsak, ko'plab blogerlarning zamonaviy kasblar orqasidan mo'may daromad topayotganini ko'rishimiz mumkin. Bu sohalar ularga moliyaviy jihatdan mustaqil bo'lish va oz vaqtda tajriba orttirish imkonini bergan.\n\nIkkinchi qarash tarafdorlari zamonaviy kasblarni tanlashda xavf-xatarlarni oldindan ko'ra oladilar. Avvalo, bu sohalar telefon, kompyuter kabi texnikalar bilan bog'liq bo'lib, ulardan chiqayotgan nurlar inson sog'ligi uchun zararlidir. Bundan tashqari texnologiyalar o'zgarib, baʼzi kasblar avtomatlashtirilishi yoki sunʼiy intellekt tomonidan bajarilishi mumkin. Hatto inson mimikalarini oʻzlashtirayotgan robotlar rivojlanib borayotgan davrda zamonaviy kasblar taraqqiyoti mavhum masala bo'lib qolmoqda.\n\nHar ikkala tomonning fikrlaridan kelib chiqadigan bo'lsak, zamonaviy kasblar tez rivojlanmoqda. Shu bilan birga ularning kelajagi noma'lum hamdir. Oliy ta'lim talab qiladigan mutaxassisliklar barqarorlik va uzoq muddatli rivojlanish imkonini beradi. Qay birini tanlash esa insonning oʻziga bog'liq.\n\nXulosa qilib aytganda, zamonaviy kasblarni tanlash har kimning ixtiyoriy tanlovi. Oliy ta'limni talab qilmaydigan kasblar qisqa muddatli maqsadlar uchun foydali bo'lishi mumkin, lekin bu kasblar insonning hayoti davomida bir umrlik faoliyat bo'la olmaydi."
    },
    {
        "title": "2. Xususiy va davlat maktablarida ta'lim sifati",
        "text": "Ayrimlar farzandlarini zamonaviy jihozlar, malakali o'qituvchilar va individual yondashuv bilan ajralib turadigan xususiy maktablarda o'qitishni afzal deb bilsa, ba'zilar davlat maktablaridagi anʼanaviy ta'lim bilan mukammal bilim olish mumkin deb hisoblashadi. Har ikki tomon ham oʻz fikrlarining asosli dalillariga ega.\n\nFarzandlarini xususiy maktablarda o'qitish tarafdori bo'lgan ota-onalar bu muassasalar koʻproq resurslar va imkoniyatlarga egaligini ta'kidlaydilar. Xususiy maktablar bir qator qulayliklarga ega. Birinchidan, ulardagi sinflarda o'quvchi sonining ozligi o'qituvchi har bir o'quvchiga alohida vaqt ajrata olishini taʼminlaydi. Natijada o'quvchilar mavzularni qiynalmay o'zlashtiradilar. Ikkinchidan, zamonaviy texnologiyalar bilan jihozlangan xonalarda ta'lim olgan o'quvchining bilim darajasi ham yuqori bo'ladi. Shu bilan birga xususiy ta'lim muassasalarida o'qish pulli bo'lgani uchun o'quvchidan ham ota-onadan ham masʼuliyatni talab qiladi. Qo'qon shahridagi \"Lider school\" xususiy maktabi o'quvchilari turli sertifikatlarni qo'lga kiritib, muddatidan oldin talaba boʻlish imkoniyatiga egaligini fikrimiz isboti sifatida keltirishimiz mumkin.\n\nDavlat maktablarida o'qishni qo'llab-quvvatlaydiganlar esa sifatli ta'lim olish uchun o'qituvchi malakasi va o'quvchi iqtidorini yetarli deb hisoblaydilar. Bunday maktablar bepul boʻlgani uchun jamiyatning salmoqli qatlamini ta'lim jarayoniga qamrab oladi. Davlat maktablarida qo'shimcha to'garaklar, sport mashg'ulotlari va madaniy tadbirlar ko'proq o'tkaziladi. Bu holat o'quvchilarning har tomonlama rivojlanishiga sabab bo'ladi. O'zbekistonda 11 yillik majburiy bepul ta'lim joriy etilgan, shuning uchun mamlakatimizda savodsizlik darajasi atigi 0.02 foizni tashkil etadi.\n\n\"Har kim o'zgarishi bilan oʻlchar\" deganlaridek, farzandlarini qanday ta'lim muassasasida o'qitish ota-onaning oʻziga bog'liq. Moliyaviy sharoiti to'g'ri kelsa, menimcha, bola xususiy maktabda o'qigani ma'qul. Chunki pulli muassasalarda berilgan bilimga yarasha talab ham kuchli bo'ladi.\n\nXulosa qilib aytganda, mukammal ta'lim olish uchun maktabning turi emas balki ta'lim jarayonini tashkil etish muhim. Xususiy maktablar esa bu borada qo'shimcha imkoniyatlar taklif qila oladi."
    },
    {
        "title": "3. Yutuqli o'yinlar va shoularning ishonchga ta'siri (1-variant)",
        "text": "Insonlar mehnat faoliyati bilan shuģullanar ekan, albatta, hordiq chiqarishga ehtiyoj sezadilar. Ba'zilar bugungi kunda ommalashishga ulgurgan yutuqli òyinlar hamda kòngilochar shoular insonlarning madaniy hordiq chiqarishlari uchun bir usul deb bilishsa, ayrimlar bu kabi sovrinli òyinlar, turli shoularni atrofdagilarga nisbatan ishonch tuyģusining yòqolishiga sabablardan biri deb kòrsatadi.\n\nBirinchi qarash tarafdorlarining fikriga kòra, vaqti-vaqti bilan shoular, yutuqli òyinlarda qatnashish insonlarning hordiq chiqarishlari uchun imkoniyatdir. Jismoniy va aqliy mehnat bilan shuģullanib, charchoqni his qilgan har qanday inson, tabiiyki, dam olishga ehtiyoj sezadi. Zangori ekran orqali namoyish etilayotgan kòngilochar dasturlar, konsertlar, shoular kòpchilikning kayfiyatiga ijobiy ta'sir kòrsatadi. Masalan, yurtdoshlarimiz orasida \"Boriga baraka\", \"Omad shou\" kabi yutuqli òyinlarda ishtirok etib, ularning kòpchiligi katta-katta sovrinlarning egalariga aylangan. Bundan tashqari, istirohat boģlarida konsertlar tashkil etilishi odamlarni biroz muddatga muammolardan chalg'itadi. Psixologlarning fikricha, shoularga qatnashuvchi insonlar orasida asabiy zo'riqishlar kamroq uchraydi.\n\nQarshi fikr tarafdorlari esa sovrinli kòrsatuvlar va shoular kundan kunga ko'payib borayotgani salbiy oqibatlarga sabab bòlishini ta'kidlaydilar. Yutuqli òyinda ishtirok etish uchun berilgan shartlarni bajarib, yillar davomida xabar kutayotganlar kòpchilikni tashkil qiladi. Bu esa tashkilotchilarga nisbatan ishonchning yòqolishiga sabab bòladi. Masalan, \"Omad shou\"da qatnashish uchun mahsulotlarni uzluksiz sotib olish \"chòntakni quritadi\". Bundan tashqari, Xonobod shahrida tashkil etilgan xalqaro konsert uchun 9 mlrd so'm ajratilgan edi. Tashqi qarz mavjud bo'lgan paytda bunday xarajatlar ortiqchadek tuyuladi. Xalqning pulini mashshoqlarga sarflagandan ko'ra qishloq yo'llarini asfalt qilish manfaatliroq bo'lar edi.\n\nMening nazarimda, sovrinli òyin tashkilotchilari faoliyatini nazoratga olish, adolat mezonlarini ishlab chiqish zarur. Donolarimiz \"Mashshog’i kòpaygan yurtning qashshog’i kòpayadi\" deb bejiz aytmagan.\n\nXulosa òrnida shuni aytmoqchimanki, inson har doim ham kòngil yozishga ehtiyoj sezadi. Faqatgina bu borada adolat va ma'naviyat kòchasidan uzoqlashmasak bòlgani."
    },
    {
        "title": "4. Yutuqli o'yinlar va tijoriy ko'ngilochar dasturlar (2-variant)",
        "text": "Turli tijoriy maqsadlarda tashkil qilinuvchi ko’ngilochar dasturlar reklama va xizmat ko’rsatish tarmog’ining asosiy bo’g’ini sifatida yangi mahsulot yoki brendni aholi orasida tanishtirish va keng targ’ib qilishda alohida ahamiyat kasb etadi. Biroq bunday shoular insonlararo munosabatlarga salbiy ta’sir qilishini ta’kidlovchi kishilar ham talaygina. Har ikkala qarashning o’z tarafdorlari va asoslovchi dalillari bisyordir.\n\nDastlab ommaviy axborot vositalarining takomili sifatida vujudga kelgan yutuqli o’yinlar keyinchalik yirik kompaniyalarning samarali targ’ibot vositasiga aylandi. Zero \"Trendymen\" nashrining yozishicha, \"Alibaba\" asoschisi Jek Ma ham bozor iqtisodiyotida mahsulotni ishlab chiqarishdan ko’ra uni sotish muhimligini alohida ta’kidlagan. Shuningdek, kichik mablag’ evaziga katta mukofotga ega bo’lish qaysidir oilaning iqtisodiy holatini yaxshilashga xizmat qilishi mumkin. Har bir yutuq summasidan davlatga 12% daromad solig’i to’lanishini inobatga olsak, qonuniy shoularning xazinaga ham hissa qo’shishi oydinlashadi.\n\n\"Mehnatdan kelsa boylik, turmush bo’lar chiroyli\" naqliga rioya qiluvchilar esa yengil-yelpi yo’llar bilan topilgan har qanday boylikka qarshi. Ular inson qisqa umrini behuda havaslar yo’lida sarflamay, mehnat qilishi kerakligini aytadilar. Tasavvur qiling, kimdir mashina olish uchun yillab pul yig’sa-yu, uning qo’shnisi bir kunda \"Boriga baraka\"da avtoulov yutib olsa. Bu jarayonda jamiyatdagi ruhiy muvozanatga putur yetadi. Zigmund Freydning fikricha, atrof-muhitdagi nohaqliklardan norozilik ong ostida yig’ilib, depressiyaga sabab bo’ladi. Sanitariya nazorat markazi ma'lumotiga ko'ra, promokod uchun sotib olingan sifatsiz mahsulotlar salomatlikka ham zarar yetkazishi mumkin.\n\nNazarimda, kapitalizm sharoitida bunday shoularni butunlay qoralash ham, ularga mukkasidan ketish ham to'g'ri emas. Davlat mazkur dasturlarning qonuniyligi va haqqoniyligini nazorat qila olish mexanizmini yaratishi zarur.\n\nSo’ngso’z o’rnida insonning qaysi yo’l bilan boylik orttirishi uning o'ziga bog’liq ekanligini ta’kidlash o’rinli. Biroq peshona teri evaziga kelgan har narsada baraka mavjudligi ham bor gap."
    },
    {
        "title": "5. Chet tilini bilish: madaniylikmi yoki moddiy ta'minot?",
        "text": "Zamonaviy dunyoda chet tillarini bilish ko‘pchilik uchun katta ahamiyat kasb etadi. Ayrimlar chet tilini o‘rganishni madaniylik va o‘zini rivojlantirishning muhim belgisi deb bilsalar, boshqalar unga ko‘proq moddiy manfaatlar uchun kerakli ko‘nikma sifatida qarashadi. Har ikki yondashuvning o‘ziga xos sabablari bor.\n\nMadaniyatli inson – bu nafaqat ona tilida so‘zlashuvchi, balki boshqa tillarni ham o‘rganish orqali turli madaniyatlarni tushuna oladigan odamdir. Chet tilini bilish insonning dunyoqarashini kengaytiradi, boshqa xalqlarning urf-odatlari, tarixi va madaniy meroslari haqida chuqurroq ma’lumot beradi. Masalan, ingliz yoki fransuz tilini bilish badiiy asarlar, filmlar va teatr durdonalarini asl tilida tushunish imkonini beradi. Bu esa insonning madaniy tajribalarini kengaytiradi va bag'rikenglik tuyg'usini yuksaltiradi.\n\nBiroq chet tilini o‘rganishga ko‘proq amaliy va moddiy nuqtayi nazardan qaraydiganlar ham bor. Ularning fikriga ko‘ra, chet tilini bilish martaba va moddiy muvaffaqiyat garovidir. Xalqaro biznes, axborot texnologiyalari, diplomatiya va turizm sohalarida chet tilini biluvchi mutaxassislar yuqori maosh va nufuzli lavozimlarga ega bo‘lishadi. Dasturchilar, tarjimonlar yoki xalqaro huquqshunoslar xorijiy tillar vositasida jahon bozoriga chiqib, oilasining moddiy ta'minotini yuksak darajada shakllantirmoqda.\n\nMenimcha, chet tilini o‘rganish har ikkala ma’noda ham muhim: bu dunyoqarashi keng, komil inson bo‘lish uchun zarur bo‘lgan fazilat, ayni paytda farovon hayot kechirishning qudratli vositasidir.\n\nXulosa qilib aytganda, chet tilini o‘rganish orqali inson nafaqat o'zga madaniyatlarni chuqur anglaydi, balki o'zining moddiy erkinligini ham mustahkamlaydi."
    },
    {
        "title": "6. Reklamaning jamiyatdagi o'rni va chegaralari",
        "text": "Reklama o’zi nima? Uning qanday xususiyatlari bor? Mazkur esseda reklamaning foydali tomonlari va unga bo'lgan ehtiyojlarni tahlil qilamiz. Televizor yoki ijtimoiy tarmoqlar qarshisida o’tirganda ko’ngilochar ko’rsatuvlar orasida reklamaning ko’pligidan noliydiganlar talaygina. Lekin masalaga biryoqlama qarash to’g’ri emas. Reklama – ishlab chiqaruvchilar va iste'molchilar o'rtasidagi eng qulay ko'prikdir.\n\nBir ishlab chiqaruvchi yangi mahsulot ishlab chiqardi, aytaylik, bolalar kiyimi. Unga yangilik kiritib, qulay bog'ichlar qo'shdi. Tadbirkorning bu yangiligini faqat do'konga kelgan cheklangan xaridorlar bilishi mumkin. Agar u yangi mahsulotini OAV va internetda reklama qilsa, millionlab oilalar bundan xabardor bo'ladi va talab o'sadi. Demak, reklama bozor iqtisodiyotining harakatlantiruvchi kuchi hisoblanadi.\n\nLekin shunday ekan deb har narsani pala-partish reklama qilaverish yaramaydi. Oila davrasida televizor tomosha qilinayotganda ayollar gigiyenik vositalari yoki noqulay mavzulardagi reklamalar berilishi milliy mentalitetimizga to'g'ri kelmaydi. O'zbekona oilaviy qadriyatlarda ota va qiz, qaynona va kelin o'rtasida bunday masalalar sir saqlanadi. Shu sababli reklama berishda efir vaqti va me'yorlar tartibga solinishi shart.\n\nReklamalar bizni texnologik va maishiy yangiliklardan ogoh qilib turadi. Yangiliklarni kuzatib borish va ulardan o'rinli foydalanish kishiga qulaylik yaratadi.\n\nXulosa qilib aytganda, reklama axborot ulashishning eng samarali qurolidir. Faqatgina uning namoyishida milliy axloq qoidalari va madaniy chegaralar qat'iy saqlanishi maqsadga muvofiqdir."
    },
    {
        "title": "7. Ko'p farzandlilik: davlat taraqqiyotimi yoki tarbiya qiyinchiligi?",
        "text": "Ba'zilar oilada farzandlarning ko'p bo'lishi jamiyat uchun foyda keltiradi va davlatni taraqqiy ettiradi deb hisoblaydi. Ayrimlar esa bolalar koʻp boʻlganda ularning barchasiga yetarli tarbiyaviy e'tibor berib bo'lmaydi degan fikrda. Har ikki yondashuv ham hayotiy haqiqatlarga tayanadi.\n\nBirinchi qarash tarafdorlari ko'p farzandlilik demografik va iqtisodiy kuch ekanini ta'kidlaydilar. Mamlakatda aholi soni va yoshlar qatlami oshsa, mehnat resurslari ko'payadi, ishlab chiqarish va yangi g'oyalar quvvati ortadi. Qolaversa, ko'p bolali oilalarda o'zaro hamjihatlik, kattaga hurmat va mehr-oqibat fazilatlari tabiiy ravishda shakllanadi. \"O'nta boʻlsa o'rni boshqa\" deb xalqimiz qadimdan ko'p farzandni ne'mat deb bilgan. Demografik o'sish sur'ati baland bo'lgan davlatlar jahon iqtisodiyotida salmoqli o'rin tutishi buning isbotidir.\n\nBiroq ikkinchi tomon vakillari moddiy va ma'naviy mas'uliyatni birinchi o'ringa qo'yadilar. Bugungi zamonaviy dunyoda bolani shunchaki dunyoga keltirish kifoya emas, unga sifatli ta'lim berish, sog'ligini asrash va shaxs sifatida tarbiyalash katta xarajat va vaqt talab etadi. Ota-ona ro'zg'or tashvishi bilan bo'lib, bolalar tarbiyasini nazoratsiz qoldirsa, bu o'smirlar orasida huquqbuzarliklar ko'payishiga olib keladi. Statistika ma'lumotlari ham qarovsiz qolgan bolalar orasida xulq og'ishi ko'proq uchrashini ko'rsatadi.\n\nMenimcha, farzandning ko'p bo'lgani yaxshi, biroq bu masalada son emas, sifat birlamchi bo'lishi zarur. Har bir ota-ona o'zining moddiy va ma'naviy quvvatini to'g'ri baholab qaror qabul qilgani ma'qul.\n\nXulosa qilib aytganda, ko'p farzandlilik jamiyatga kuch berishi mumkin, faqat har bir bolaga munosib ta'lim va tarbiya kafolatlangan taqdirdagina bu taraqqiyot omiliga aylanadi."
    },
    {
        "title": "8. Ko'p qavatli uylar yoki shaxsiy hovlilar?",
        "text": "Hozirgi kunda ko'p qavatli uylar qurilishining avj olishi ko'plab shaharlarda keng ko'lamli o'zgarishlarga sabab bo'lmoqda. Bu kabi inshootlar yer maydonidan tejamkorlik bilan foydalanish imkonini beradi. Ammo aholining salmoqli qismi bunday uylar o'rniga qulaylik va xotirjamlik manbayi bo'lgan xususiy hovli yoki manzarali xonadonlarni afzal ko'radi.\n\nKo'p qavatli uylar shahar hududini haddan tashqari kengaytirmasdan, mavjud yer maydonida ko'proq aholini uy-joy bilan ta'minlashga xizmat qiladi. Zamonaviy ko'p qavatli turar joy majmualari o'z hududida bog'cha, maktab, savdo va dam olish maskanlarini birlashtirib, aholiga katta qulaylik yaratmoqda. Toshkent shahrida qad rostlagan \"Nest One\", \"Tashkent City\" kabi zamonaviy majmualar shahar dizayniga yangicha tus berib, uning iqtisodiy jozibadorligini oshirmoqda.\n\nShunga qaramay, ko'pchilik uchun shaxsiy hovli va tomorqa yerlari bebaho qadriyatdir. Birinchidan, xususiy hovli shovqindan yiroq, toza havo va kenglik baxsh etadi. Ikkinchidan, o'zbekona turmush tarzida hovli – an'analar va mehr-oqibat makonidir. Oilalar tomorqada ekin ekib, issiqxona tashkil qilib, ro'zg'origa qo'shimcha daromad keltiradi. Qolaversa, xususiy hovlida inson o'zini to'la erkin va tabiatga yaqin his qiladi.\n\nMenimcha, shahar markazlarida zamonaviy ko'p qavatli uylarning barpo etilishi zarurat, ammo shahar chetlarida xususiy hovli-joylar va yashil hududlarning saqlab qolinishi ham insonlar salomatligi uchun o'ta muhimdir.\n\nXulosa qilib aytganda, urbanizatsiya va milliy qadriyatlar o'rtasida muvozanat bo'lishi kerak. Har ikki turdagi maskan o'z o'rnida jamiyat taraqqiyotiga xizmat qiladi."
    },
    {
        "title": "9. Kredit: orzular ro'yobimi yoki moliyaviy qiyinchilik?",
        "text": "Bugungi kunda odamlarning yaxshi yashashlari va tadbirkorlik qilishlari uchun barcha moliyaviy vositalar ishga solinmoqda. Aksariyat kishilar kredit olish ko'p yillik muammolarni tezkor hal etishning qulay yo'li desa, boshqalar uni ortiqcha xarajat va qaramlik deb hisoblaydi. Har ikki qarashning ham o'z asoslari mavjud.\n\nKredit tizimi fuqarolarga yillar davomida to'plab bo'lmaydigan yirik mablag'ni darhol qo'lga kiritish va ehtiyojni qondirish imkonini beradi. Xususan, ipoteka kreditlari orqali ko'plab yosh oilalar o'z shaxsiy uy-joyiga ega bo'lmoqda. Shuningdek, tadbirkorlik uchun ajratilgan imtiyozli kreditlar yangi ish o'rinlari yaratish va biznesni oyoqqa turg'azishda beqiyos ahamiyatga ega. Kichik to'lovlarni oylab to'lab borish orqali inson o'z rejalari va orzularini kechiktirmasdan amalga oshiradi.\n\nBiroq kreditning jiddiy xavf-xatarlari ham bor. Bank foizlari tufayli qarz oluvchi olingan summadan ancha ko'p mablag' qaytarishga majbur bo'ladi. Kutilmagan moliyaviy tanglik, ishsizlik yoki daromadning pasayishi natijasida uzoq yillik qarzdorlik inson ruhiyatiga og'ir zarba beradi. \"Qarzi borning uyqusi yo'q\" deganlaridek, o'z moliyaviy imkoniyatini to'g'ri hisoblamay kreditga botish oilalarda parokandalikni keltirib chiqarishi mumkin.\n\nNazarimda, kredit faqatgina daromad keltiruvchi biznes yoki birlamchi boshpana uchun olingandagina o'zini oqlaydi. Dabdabali to'y yoki qimmatbaho buyumlar uchun kredit olish esa aslo to'g'ri emas.\n\nXulosa qilib aytganda, kredit – to'g'ri ishlatilsa qudratli vosita, pala-partish foydalanilsa moliyaviy qafasdir. Har bir qadam puxta hisob-kitob asosida qo'yilishi shart."
    },
    {
        "title": "10. Jinoyatlarni OAV orqali oshkora ko'rsatish: ogohlikmi yoki targ'ibot?",
        "text": "Ijtimoiy tarmoqlar va OAVlarda turli xabarlarga duch kelamiz. Bularning orasida eng ko'p muhokamalarga sabab bo'layotgani jinoyat va huquqbuzarliklar bilan bog'liq lavhalardir. Ko'pchilik sodir etilgan jinoyatlarni ommaga ochiq ko'rsatish salbiy holatlarning ko'payishiga sabab bo'ladi desa, ba'zilar bu jarayon jamoatchilikni ogohlikka chorlaydi deb biladi.\n\nBirinchi qarash tarafdorlarining fikriga ko'ra, jinoyatlarning tafsilotlari bilan ko'rsatilishi yoshlar ongiga salbiy ta'sir ko'rsatadi. Birinchidan, ayrim tajribasiz o'smirlar jinoyat sodir etish usullarini o'rganib olishi mumkin. Ikkinchidan, shafqatsizlik sahnalarining muntazam berilishi jamiyatda agressiyani odatiy holga aylantirib, odamlar diydasini qotiradi. Televideniyedagi turli ko'rsatuvlar orqali xavfli xatti-harakatlarning tinimsiz yoritilishi insonlarda atrofdagilarga nisbatan ishonchsizlik va qo'rquvni kuchaytiradi.\n\nQarshi fikr tarafdorlari esa jinoyat sodir etgan shaxslarning qilmishi va ularga berilgan jazo ochiq ko'rsatilishi shart deb hisoblaydilar. Bu, eng avvalo, boshqalarga dars bo'ladi. \"Jinoyat jazosiz qolmaydi\" degan haqiqatni ko'rgan kishi egri yo'ldan qaytadi. Shuningdek, firibgarlik yoki o'g'irlik usullaridan xabardor bo'lgan fuqarolar kundalik hayotda hushyorroq bo'lishadi. Huquq-tartibot organlarining tezkor choralari haqidagi rasmiy bayonotlar jamiyatda adolatga bo'lgan ishonchni mustahkamlaydi.\n\nMening fikrimcha, jinoyatlarni yoritishda me'yor bo'lishi kerak. Qonunbuzarlik oqibati va jazosi ko'rsatilishi lozim, ammo jinoyatni qanday amalga oshirish usullari va qonli lavhalar qat'iyan cheklanishi zarur.\n\n\"Ogohlik – davr talabi\" ekani rost, faqat axborot uzatishda yosh avlod tarbiyasi va ruhiyatini asrash bosh mezon bo'lib qolishi shart."
    }
]

def update_sample_essays_bank():
    # 11 dan 21 gacha bo'lgan qolgan barcha taqdim etilgan esselarni bazaga to'liq jamlash
    extra_essays = [
        ("11. Oilaviy mojarolar aks etgan videolarning ijtimoiy tarmoqlarda tarqalishi", "Bugungi kunda ijtimoiy tarmoqlarda oilaviy mojarolar aks etgan sahnalar tez-tez tarqalib turadi. Ayrimlar bu videolar jamiyat ma'naviyatiga putur yetkazadi desa, boshqalar muammolarni fosh etishda foydali deb biladi. Oila muqaddas dargoh bo'lib, uning ichki sirlari ommaga doston qilinishi oila institutini zaiflashtiradi. Bolalar ruhiyatiga shikast yetadi. Ammo zo'ravonlik holatlarining tarqalishi huquqiy jazo muqarrarligini ta'minlashga xizmat qilishi ham mumkin. Shaxsiy hayot daxlsizligi qat'iy saqlanishi shart."),
        ("12. Bitta kasbning mohir ustasi bo'lishmi yoki bir necha kasb egasi?", "Zamonaviy dunyoda muvaffaqiyatga erishish uchun bir kasbning chuqur bilimdoni bo'lish kerakmi yoki ko'p qirrali bo'lish foydaliroqmi? Bitta sohani mukammal egallagan shaxs, masalan, mohir jarroh yoki tajribali muhandis katta ehtirom va daromadga ega bo'ladi. Biroq zamon tez o'zgarayotgani sababli, bir necha ko'nikmani (masalan, dasturlash va iqtisodiyot) uyg'unlashtirgan kadrlar mehnat bozorida yanada moslashuvchan bo'ladilar. Asosiysi, inson o'z yo'lini ongli tanlashi lozim."),
        ("13. Sun'iy intellektning insoniyatga ijobiy va salbiy ta'sirlari", "XXI asrda sun'iy intellekt ish unumdorligini oshirib, og'ir jarayonlarni yengillatmoqda. Tibbiyotda aniq tashxis qo'yish, ta'limda individual o'rganish imkonini bermoqda. Biroq Jahon Iqtisodiy Forumi hisobotlarida ta'kidlanganidek, millionlab ish o'rinlarining qisqarishi va kamharakatlilik xavfi mavjud. Sun'iy intellekt inson o'rnini bosuvchi emas, unga ko'makchi bo'lib xizmat qilishi lozim."),
        ("14. Plastik qadoqdagi suv yoki vodoprovod suvi (1-tahlil)", "Suv – hayot manbayi. Filtrlangan plastik qadoqdagi suv toza va olib yurishga qulay, ammo yiliga millionlab tonna plastik chiqindining tabiatga tashlanishiga sabab bo'lmoqda. Vodoprovod suvi esa iqtisodiy tejamkor, ammo infratuzilma eskirgan joylarda quvurlardagi zang va bakteriyalar salomatlikka xavf tug'diradi. Har ikki manbadan oqilona foydalanish va suvni tejash zarur."),
        ("15. Plastik qadoqdagi suv yoki vodoprovod suvi (2-tahlil)", "JSST mutaxassislari qadoqlangan suvlarning minerallarga boy va xavfsiz ekanini tasdiqlaydi. Ammo quduq va vodoprovod suvi ota-bobolarimizdan qolgan an'anaviy ne'matdir. Tozalik mezonlariga rioya qilingan taqdirda, vodoprovod suvi ham foydalanishga to'la yaroqlidir."),
        ("16. Ta'limda milliy usullarni sayqallashmi yoki xorij tajribasimi?", "Abdulla Avloniy va jadidlar o'qitishda milliy qadriyatlarni markazga qo'yganlar. Bugungi kunda esa Finlyandiya va Singapur kabi davlatlarning ilg'or ta'lim texnologiyalaridan andoza olinmoqda. Eng to'g'ri yo'l – xorijning ilg'or metodikasini milliy mentalitetimiz va o'zligimiz bilan uyg'unlashtirishdir."),
        ("17. An'anaviy to'ylar va zamonaviy ixcham marosimlar", "Nahor oshi, kelin salom kabi milliy to'y marosimlari o'zligimiz ko'zgusidir. Ammo G'arb davlatlaridagi kabi ixcham to'ylar moliyaviy isrofgarchilik va qarzga botishdan saqlaydi. To'ylarni qadriyatlarga sodiq holda, ortiqcha dabdabasiz va me'yorida o'tkazish eng oqilona yo'ldir."),
        ("18. Zamonaviy audio kitoblar va an'anaviy mutolaa", "Audio kitoblar yo'lda, yumush bajarayotganda vaqtni tejash imkonini beradi. Biroq qog'oz kitobni varaqlab o'qish inson diqqatini chuqurroq jamlashga, tafakkur va xotirani charxlashga yordam beradi. Har ikki mutolaa shakli kitobxonlik madaniyatini yuksaltirishga xizmat qiladi."),
        ("19. Tarbiyada erkinlik: shaxs kamoloti yoki intizomsizlik? (1-qarash)", "Erkinlik bolaning mustaqil qaror qabul qilishi va ijodkorligini o'stiradi. Ammo me'yorsiz erkinlik mas'uliyatsizlik va tarbiyasizlikka yetaklashi mumkin. Qat'iy intizom va mehrga asoslangan erkinlikning oltin o'rtalig'ini topish ota-onaning asosiy burchidir."),
        ("20. Tarbiyada erkinlik va sharqona odob (2-qarash)", "Kaykovusning 'Qobusnoma' asarida pand-nasihat va o'git ustuvor bo'lganidek, sharqona tarbiya kattalarga hurmat va kamsuqumlikni talab qiladi. Bolaga me'yorida erkinlik berilsagina, u jamiyatga foydali inson bo'lib voyaga yetadi."),
        ("21. Inson omili va Yer sayyorasi ekologiyasi", "Sanoat va texnologiya rivoji tabiatga ziyon yetkazmoqda, iqlim isishi va chiqindilar global muammoga aylandi. Shu bilan birga, 'Yashil makon' kabi tashabbuslar va toza energiya texnologiyalari inson faoliyati orqali zaminni asrab qolish mumkinligini isbotlamoqda."),
        ("22. O'qish davrida ishlash: tajriba orttiradimi yoki chalg'itadimi?", "Talabalik davrida mehnat qilish moliyaviy mustaqillik va amaliy tajriba beradi. Biroq asosiy diqqatni fanga qaratmay, faqat pul topishga chalg'ish chuqur bilim olishga to'sqinlik qiladi. Nazariya va amaliyot uyg'un bo'lgandagina mukammal mutaxassis yetishib chiqadi.")
    ]
    for t, txt in extra_essays:
        SAMPLE_ESSAYS_BANK.append({"title": t, "text": txt})

update_sample_essays_bank()

# --- MUKAMMAL MAVZULAR KATALOGI ---
THEME_CATALOG = {
    "cat_fonetika": {
        "title": "🗣 Fonetika, orfoepiya va imlo qoidalari",
        "prompt": "Fonetika: unli va undoshlar tasnifi, tovush o'zgarishlari, urg'u hamda rasmiy imlo mezonlari"
    },
    "cat_leksika": {
        "title": "📖 Leksikologiya, frazeologiya va paronimlar",
        "prompt": "Leksikologiya: o'z va o'zlashgan qatlam, ma'nodosh, shakldosh, zid ma'noli so'zlar, paronimlar va iboralar"
    },
    "cat_morf_mustaqil": {
        "title": "🧩 Morfologiya: Mustaqil so'z turkumlari",
        "prompt": "Mustaqil so'z turkumlari: ot, sifat, son, olmosh, ravish hamda fe'l nisbatlari, vazifa shakllari"
    },
    "cat_morf_yordamchi": {
        "title": "🔗 Morfologiya: Yordamchi so'zlar va alohida guruh",
        "prompt": "Yordamchi so'zlar, modal so'zlar, taqlidlar va undov so'zlar uslubiyati hamda imlosi"
    },
    "cat_sintaksis": {
        "title": "📐 Sintaksis: Gap bo'laklari va qo'shma gaplar",
        "prompt": "Sintaksis: so'z birikmasi, gap bo'laklari, ergashgan qo'shma gaplar va tinish belgilari"
    },
    "cat_mumtoz": {
        "title": "📜 Mumtoz adabiyot va badiiy san'atlar",
        "prompt": "Mumtoz adabiyot: Navoiy va Bobur ijodi, aruz vazni, she'riy janrlar va badiiy san'atlar"
    },
    "cat_jadid": {
        "title": "💡 Jadid va XX asr o'zbek adabiyoti",
        "prompt": "Jadid va XX asr adabiyoti: Behbudiy, Avloniy, Fitrat, Cho'lpon, Qodiriy, Oybek asarlari tahlili"
    }
}

HISTORICAL_EPOCHS = [
    {"epoch": "Qadimgi va ilk o'rta asrlar turkiy yozma obidalari", "sources": "Qutadg'u bilig, Devonu lug'atit turk, Hibat ul-haqoyiq"},
    {"epoch": "Temuriylar davri mumtoz adabiyoti", "sources": "Alisher Navoiy, Zahiriddin Muhammad Bobur asarlari"},
    {"epoch": "XVII-XIX asrlar adabiyoti", "sources": "Mashrab, Ogahiy, Munis, Nodirabegim asarlari"},
    {"epoch": "Jadid ma'rifatparvarlik davri", "sources": "Behbudiy, Avloniy, Fitrat, Cho'lpon publitsistikasi"},
    {"epoch": "XX asr o'zbek adabiyoti durdonalari", "sources": "Qodiriy, Oybek, G'afur G'ulom, Erkin Vohidov, Abdulla Oripov"}
]

# --- BANNER-CARD BILAN ASOSIY BO'LIMLARNI YUBORISH ---
def send_section_card(chat_id, group_name):
    if group_name == "abituriyent":
        img = BANNER_IMAGES["abituriyent"]
        caption = (
            "╭──── 🎒 **ABITURIYENT VA SERTIFIKAT MARKAZI** ────╮\n\n"
            "▫️ **🎖 Milliy sertifikat** (50 ballik esse tekshiruvi, mavzular va namunalar)\n"
            "▫️ **📖 So'z izohi (O'TIL) & Imlo** mezonlari\n"
            "▫️ **🧠 BMB 30 talik Test:** Davlat imtihoni standarti (30 soniya)\n"
            "▫️ **📚 Mavzuli BMB Test:** Mukammal katalog yoki erkin mavzu\n\n"
            "👇 *Kerakli bo'limni tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="🎖 Milliy sertifikat (Esse markazi)", callback_data="btn_open_milliy_sertifikat"),
            tele_types.InlineKeyboardButton(text="📖 So'z izohi (O'TIL) & Imlo", callback_data="btn_izoh"),
            tele_types.InlineKeyboardButton(text="🧠 BMB Umumiy 30 talik Test (№)", callback_data="btn_bmb_gen"),
            tele_types.InlineKeyboardButton(text="📚 Mavzulashtirilgan BMB Test (30 ta)", callback_data="btn_bmb_themed_hub"),
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)
    elif group_name == "talaba":
        img = BANNER_IMAGES["talaba"]
        caption = (
            "╭──── 🎓 **TALABALAR VA FILOLOGLAR KABINETI** ────╮\n\n"
            "▫️ Mumtoz g'azaliyot badiiyati va poetik san'atlar\n"
            "▫️ Aruz tizimi: hijolar vazni, bahrlar va taf'ilalar\n"
            "▫️ Eski turkiy til manbalari hamda nodir leksik qatlam\n"
            "▫️ Rahmatullayev etimologik lug'ati asosidagi tahlillar\n\n"
            "👇 *Kerakli tahlil turini tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=2)
        markup.row(
            tele_types.InlineKeyboardButton(text="📜 G'azal tahlili", callback_data="btn_gazal"),
            tele_types.InlineKeyboardButton(text="📐 Aruz hisoblagich", callback_data="btn_aruz")
        )
        markup.row(
            tele_types.InlineKeyboardButton(text="🏛 Qadimgi turkiy", callback_data="btn_qadim"),
            tele_types.InlineKeyboardButton(text="🔍 So'z etimologiyasi", callback_data="btn_etim")
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)
    elif group_name == "oqituvchi":
        img = BANNER_IMAGES["oqituvchi"]
        caption = (
            "╭──── 👨‍🏫 **METODIST VA O'QITUVCHILAR KABINETI** ────╮\n\n"
            "▫️ Yangi DTS bo'yicha 45 daqiqalik dars konspektlari\n"
            "▫️ Zamonaviy interfaol metodlar (Blum, FSMU, Ven diagrammasi)\n"
            "▫️ **Attestatsiya 40 talik Testi:** Y1 (Bilish), Y2 (Qo'llash), Y3 (Mulohaza)\n\n"
            "👇 *Kerakli amaliyotni tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="📋 45 daqiqalik Dars Ishlanmasi", callback_data="btn_konspekt"),
            tele_types.InlineKeyboardButton(text="🎯 Interfaol Pedagogik Metod", callback_data="btn_metod"),
            tele_types.InlineKeyboardButton(text="📝 Attestatsiya Testi (40 ta Y1, Y2, Y3)", callback_data="btn_attest")
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)
    elif group_name == "izlanuvchi":
        img = BANNER_IMAGES["izlanuvchi"]
        caption = (
            "╭──── 🔬 **ILMIY TADQIQOT VA DOKTORANTURA** ────╮\n\n"
            "▫️ OAK talabidagi ilmiy maqola (IMRAD standarti rejasi)\n"
            "▫️ Xalqaro va Respublika ilmiy konferensiya tezislari\n"
            "▫️ Dissertatsiya ilmiy apparati va metodologiya yo'riqnomasi\n\n"
            "👇 *Loyihalashtirmoqchi bo'lgan ilmiy yo'nalishni tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="📑 Ilmiy Maqola Konstruktori (OAK)", callback_data="btn_maqola"),
            tele_types.InlineKeyboardButton(text="📄 Konferensiya Tezisi Loyihasi", callback_data="btn_tezis")
        )
        bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)

# --- 🎖 MILLIY SERTIFIKAT MARKAZI VA ICHKI BO'LIMLAR ---
def send_milliy_sertifikat_hub(chat_id):
    img = BANNER_IMAGES["milliy_sertifikat"]
    caption = (
        "╭──── 🎖 **MILLIY SERTIFIKAT ASOSIY BO'LIMI** ────╮\n\n"
        "Ona tili va adabiyoti fanidan Milliy sertifikat 50 ballik esse platformasi:\n\n"
        "▫️ **📝 Esse tekshiruvchi (50 ballik)** — yozgan essengizni rasmiy 4 ta mezon bo'yicha baholatish;\n"
        "▫️ **🎯 Esse mavzulari (19+ ta)** — rasmiy imtihonda tushgan dolzarb mavzular va AI qidiruvi;\n"
        "▫️ **📖 50 ballik namunaviy esselar** — 21 ta to'liq professional namunalar va AI yozib berish xizmati.\n\n"
        "👇 *Kerakli xizmatni tanlang:* \n"
        "╰─────────────────────────────────────────────╯"
    )
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="📝 Esse tekshiruvchi (50 ballik)", callback_data="ms_esse_check"),
        tele_types.InlineKeyboardButton(text="🎯 Esse mavzulari (Rasmiy & AI)", callback_data="ms_topics_0"),
        tele_types.InlineKeyboardButton(text="📖 Namunaviy esselar (50 ballik)", callback_data="ms_samples_0"),
        tele_types.InlineKeyboardButton(text="🔙 Abituriyent bo'limiga qaytish", callback_data="back_to_abituriyent")
    )
    bot.send_photo(chat_id, img, caption=caption, parse_mode="Markdown", reply_markup=markup)

def send_topics_page(chat_id, page=0):
    per_page = 5
    total = len(OFFICIAL_ESSAY_TOPICS)
    total_pages = (total + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, total)
    
    text = f"🎯 **MILLIY SERTIFIKAT RASMIY ESSE MAVZULARI**\n"
    text += f"📄 Sahifa: `{page + 1}/{total_pages}` (Jami: {total} ta mavzu)\n\n"
    
    for i in range(start, end):
        text += f"**{i+1}.** {OFFICIAL_ESSAY_TOPICS[i]}\n\n"
        
    markup = tele_types.InlineKeyboardMarkup(row_width=2)
    nav_btns = []
    if page > 0:
        nav_btns.append(tele_types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ms_topics_{page - 1}"))
    if page + 1 < total_pages:
        nav_btns.append(tele_types.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"ms_topics_{page + 1}"))
    if nav_btns:
        markup.row(*nav_btns)
        
    markup.add(
        tele_types.InlineKeyboardButton(text="🎲 AI orqali yangi mavzu topish", callback_data="ms_ai_new_topic"),
        tele_types.InlineKeyboardButton(text="🔙 Milliy sertifikat markaziga", callback_data="btn_open_milliy_sertifikat")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

def send_samples_page(chat_id, page=0):
    per_page = 6
    total = len(SAMPLE_ESSAYS_BANK)
    total_pages = (total + per_page - 1) // per_page
    start = page * per_page
    end = min(start + per_page, total)
    
    text = f"📖 **50 BALLIK NAMUNAVIY ESSELAR KUTUBXONASI**\n"
    text += f"📄 Sahifa: `{page + 1}/{total_pages}` (Jami: {total} ta tayyor esse)\n\n"
    text += "Quyidagi ro'yxatdan kerakli esseni tanlab, to'liq matnini o'rganishingiz mumkin:\n"
    
    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    for idx in range(start, end):
        s_item = SAMPLE_ESSAYS_BANK[idx]
        markup.add(tele_types.InlineKeyboardButton(text=f"📌 {s_item['title'][:45]}", callback_data=f"ms_read_{idx}"))
        
    nav_btns = []
    if page > 0:
        nav_btns.append(tele_types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ms_samples_{page - 1}"))
    if page + 1 < total_pages:
        nav_btns.append(tele_types.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"ms_samples_{page + 1}"))
    if nav_btns:
        markup.row(*nav_btns)
        
    markup.add(
        tele_types.InlineKeyboardButton(text="✍️ Yangi mavzuga AI orqali esse yozdirish", callback_data="ms_ai_write_new"),
        tele_types.InlineKeyboardButton(text="🔙 Milliy sertifikat markaziga", callback_data="btn_open_milliy_sertifikat")
    )
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=markup)

# --- GEMINI SISTEMA KO'RSATMASI ---
SYSTEM_INSTRUCTION = (
    "Siz O'zbekiston Respublikasi BMB (DTM) va Milliy sertifikat bosh eksperti, "
    "filolog-metodist va baholash komissiyasi a'zosisiz.\n\n"
    "ESSE TEKSHIRUVCHISI MEZONI (50 BALLIK QAT'IY STANDART):\n"
    "Har qanday esseni quyidagi 4 ta mezon bo'yicha tahlil qilib, ball qo'ying:\n"
    "1. Mavzuning ochilishi va muammo mohiyati (15 ball);\n"
    "2. Dalillar va asoslash (faktlar, shaxsiy va tarixiy misollar) (10 ball);\n"
    "3. Mantiqiy izchillik va kompozitsiya (kirish, asosiy qism, xulosa) (10 ball);\n"
    "4. Til va uslub, savodxonlik (orfoepiya, imlo, tinish belgilari) (15 ball).\n"
    "Har bir mezon bo'yicha kamchiliklarni alohida ko'rsatib, umumiy ball va tavsiya bering.\n\n"
    "NAMUNAVIY ESSE MEZONI:\n"
    "Berilgan mavzu bo'yicha Milliy sertifikat imtihoni uchun 50 ballik mezonlarga 100% mos keladigan "
    "kirish (har ikki qarash ifodasi), asosiy qism (1- va 2-qarash dalillari), muallif munosabati va "
    "teran xulosadan iborat mukammal esse yozing."
)

def generate_ai_content(prompt_text):
    if check_security_violation(prompt_text):
        return SECURITY_WARNING

    full_prompt = f"{prompt_text}\n\nTalablar: Telegram Markdown formatida, ko'rkam sarlavhalar va ilmiy uslubda bo'lsin."
    models = ["gemini-3.6-flash"]
    for model_name in models:
        for _ in range(3):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.4)
                )
                if response and response.text:
                    return response.text.strip() + IMZO
            except Exception:
                time.sleep(2)
    return "Hozirda AI xizmatida yuqori yuklama kuzatilmoqda. Birozdan so'ng qayta urinib ko'ring."

# --- QADAMLI DINAMIK YUKLANISH ANIMATSIYASI ---
def dynamic_ai_delivery(chat_id, prompt_text, user_id, category_tag):
    if check_security_violation(prompt_text):
        bot.send_message(chat_id, SECURITY_WARNING, parse_mode="Markdown")
        return

    status_msg = bot.send_message(chat_id, "⏳ *Milliy sertifikat mezonlari va dalillar tahlil qilinmoqda...*", parse_mode="Markdown")
    time.sleep(1.2)
    try:
        bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_msg.message_id,
            text="🔍 *Kompozitsiya va 50 ballik mezonlar qoliplashmoqda...*",
            parse_mode="Markdown"
        )
    except Exception:
        pass
    time.sleep(1.2)

    try:
        raw_result = generate_ai_content(prompt_text)
        try:
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            pass

        styled_text = (
            "╭── 📝 **MILLIY SERTIFIKAT EKSPERT XULOSASI** ──╮\n\n"
            f"**>** {raw_result.strip()}\n\n"
            "╰──────────────────────────────────────────╯\n"
            f"🏛 **Rasmiy kanal:** `{CHANNEL_USERNAME}`"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            tele_types.InlineKeyboardButton(text="🔄 Yangi tahlil", callback_data="ms_esse_check"),
            tele_types.InlineKeyboardButton(text="📖 Namunaviy esselar", callback_data="ms_samples_0")
        )
        markup.add(tele_types.InlineKeyboardButton(text="🔙 Milliy sertifikat markaziga", callback_data="btn_open_milliy_sertifikat"))
        bot.send_message(chat_id, styled_text, parse_mode="Markdown", reply_markup=markup)
    except Exception as e:
        bot.send_message(chat_id, f"❌ Xatolik yuz berdi: {e}")

# --- CALLBACK TUGMALARNI BOSHQARISH ---
@bot.callback_query_handler(func=lambda call: call.data.startswith(("btn_", "ms_", "back_to_abituriyent", "seltheme_", "theme_")))
def callback_all_buttons(call):
    cid = call.message.chat.id
    uid = call.from_user.id
    data = call.data

    if data == "btn_open_milliy_sertifikat":
        send_milliy_sertifikat_hub(cid)

    elif data == "back_to_abituriyent":
        send_section_card(cid, "abituriyent")

    elif data == "ms_esse_check":
        msg = bot.send_message(
            cid, 
            "📝 **50 Ballik Esse Tekshiruvi:**\n\n"
            "Esse mavzusi va matningizni to'liq yuboring.\n"
            "Ekspert tizimimiz uni 4 ta rasmiy mezon (Mavzu, Dalillar, Mantiq, Savodxonlik) bo'yicha tahlil qilib beradi:"
        )
        p = "Ushbu esse matnini Milliy sertifikatning 50 ballik mezoni bo'yicha to'liq tekshirib, ball qo'ying va xatolarini ko'rsating:\n\n'{input}'"
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "esse"))

    elif data.startswith("ms_topics_"):
        page = int(data.replace("ms_topics_", ""))
        send_topics_page(cid, page=page)

    elif data == "ms_ai_new_topic":
        bot.answer_callback_query(call.id, "Yangi mavzu qidirilmoqda...")
        p = "Milliy sertifikat va BMB imtihonlari mezoniga mos, jamiyatdagi dolzarb ikki tomonlama bahsli yangi 1 ta original esse mavzusi tuzing va uning qisqacha tahliliy yo'nalishini bering."
        dynamic_ai_delivery(cid, p, uid, "ai_topic")

    elif data.startswith("ms_samples_"):
        page = int(data.replace("ms_samples_", ""))
        send_samples_page(cid, page=page)

    elif data.startswith("ms_read_"):
        idx = int(data.replace("ms_read_", ""))
        if idx < len(SAMPLE_ESSAYS_BANK):
            sample = SAMPLE_ESSAYS_BANK[idx]
            text = (
                f"📌 **NAMUNAVIY ESSE (50 BALLIK STANDART)**\n\n"
                f"🏷 **Mavzu:** *{sample['title']}*\n\n"
                f"**>** {sample['text']}\n\n"
                f"🏛 **Rasmiy kanal:** `{CHANNEL_USERNAME}`"
            )
            markup = tele_types.InlineKeyboardMarkup(row_width=1)
            markup.add(tele_types.InlineKeyboardButton(text="🔙 Namunalar ro'yxatiga qaytish", callback_data="ms_samples_0"))
            bot.send_message(cid, text, parse_mode="Markdown", reply_markup=markup)

    elif data == "ms_ai_write_new":
        msg = bot.send_message(
            cid, 
            "✍️ Qaysi mavzuda 50 ballik namunaviy esse kerak? Mavzuni yozib yuboring:\n"
            "*(Bot barcha dalillari, kompozitsiyasi va xulosalari bilan mukammal yozib beradi)*"
        )
        p = "Ushbu mavzuda Milliy sertifikat imtihoni uchun 50 ballik mezonlarga 100% mos keladigan namunaviy mukammal esse yozib bering:\n'{input}'"
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "sample_write"))

    # Mavzuli testlar hubi va katalog
    elif data == "btn_bmb_themed_hub":
        caption = (
            "╭── 📚 **MAVZULASHTIRILGAN BMB TEST MARKAZI** ──╮\n\n"
            "Ona tili va adabiyoti fanidan 30 talik test topshirish uchun "
            "o'zingizga qulay usulni tanlang:\n\n"
            "1️⃣ **Mavzular katalogidan tanlash** — 5-11-sinf darsliklarining asosiy bo'limlari bo'yicha ro'yxat;\n"
            "2️⃣ **Mavzuni o'zingiz kiritish** — istalgan dars mavzusini yozasiz, bot test tuzib beradi.\n\n"
            "👇 *Tanlang:* \n"
            "╰─────────────────────────────────────────────╯"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="📂 Mavzular Katalogidan tanlash", callback_data="theme_open_catalog"),
            tele_types.InlineKeyboardButton(text="✍️ O'zim yangi mavzu kiritaman", callback_data="theme_custom_input"),
            tele_types.InlineKeyboardButton(text="🔙 Abituriyent bo'limiga qaytish", callback_data="back_to_abituriyent")
        )
        bot.send_message(cid, caption, parse_mode="Markdown", reply_markup=markup)

    elif data == "theme_open_catalog":
        caption = "╭── 📂 **5-11-SINF DARSLIKLARI MAVZULAR KATALOGI** ──╮\n\nKerakli bo'limni tanlang:\n╰──────────────────────────────────────────────╯"
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        for cat_key, cat_data in THEME_CATALOG.items():
            markup.add(tele_types.InlineKeyboardButton(text=cat_data["title"], callback_data=f"seltheme_{cat_key}"))
        markup.add(tele_types.InlineKeyboardButton(text="🔙 Orqaga", callback_data="btn_bmb_themed_hub"))
        bot.send_message(cid, caption, parse_mode="Markdown", reply_markup=markup)

    elif data == "theme_custom_input":
        msg = bot.send_message(cid, "✍️ Qaysi darslik mavzusidan 30 talik test tuzmoqchisiz? Yozib yuboring:")
        def start_custom_theme(m):
            theme = m.text.strip()
            quiz_title = f"«{theme}» mavzusi bo'yicha test (30 ta)"
            bot.send_message(cid, f"⏳ *«{theme}» bo'yicha test shakllanmoqda... Har bir savolga ⏳ 30 soniya!*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(theme)
                offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
            except Exception as e:
                bot.send_message(cid, f"❌ Xatolik: {e}")
        bot.register_next_step_handler(msg, start_custom_theme)

    elif data.startswith("seltheme_"):
        cat_key = data.replace("seltheme_", "")
        cat_info = THEME_CATALOG.get(cat_key)
        if cat_info:
            quiz_title = f"{cat_info['title']} (30 ta)"
            bot.send_message(cid, f"⏳ *{cat_info['title']} bo'yicha 30 talik test tuzilmoqda...*", parse_mode="Markdown")
            try:
                questions = get_themed_bmb_questions(cat_info["prompt"])
                offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
            except Exception as e:
                bot.send_message(cid, f"❌ Xatolik: {e}")

    # Boshqa umumiy menyu tugmalari
    elif data == "btn_bmb_gen":
        bot.send_message(cid, "⏳ *BMB standarti bo'yicha 30 talik test shakllanmoqda...*", parse_mode="Markdown")
        try:
            bmb_num = get_next_quiz_number("bmb_30")
            quiz_title = f"№{bmb_num} BMB 30 talik test"
            questions = get_themed_bmb_questions("5-11-sinf barcha bo'limlari")
            offer_quiz_dispatch(cid, uid, questions, duration_per_q=30, title=quiz_title)
        except Exception as e:
            bot.send_message(cid, f"❌ Xatolik: {e}")

    elif data == "btn_attest":
        bot.send_message(cid, "⏳ *Attestatsiya spetsifikatsiyasi bo'yicha 40 ta Y1, Y2, Y3 testlari shakllanmoqda...*", parse_mode="Markdown")
        try:
            att_num = get_next_quiz_number("attestation")
            quiz_title = f"№{att_num} Attestatsiya Y1, Y2, Y3 testi"
            questions = get_attestation_questions()
            offer_quiz_dispatch(cid, uid, questions, duration_per_q=40, title=quiz_title)
        except Exception as e:
            bot.send_message(cid, f"❌ Xatolik: {e}")

    elif data == "btn_izoh":
        msg = bot.send_message(cid, "📖 Izohini yoki imlosini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "O'zbek tilining izohli lug'ati va imlo qoidalari asosida '{input}' so'zini to'liq sharhlang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "izoh_imlo"))

    elif data == "btn_gazal":
        msg = bot.send_message(cid, "✍️ Badiiy tahlil qilmoqchi bo'lgan mumtoz baytingizni yuboring:")
        p = "Ushbu baytni badiiy tahlil qiling: '{input}'. San'atlari va so'zlar sharhini bering."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "gazal"))

    elif data == "btn_aruz":
        msg = bot.send_message(cid, "✍️ Aruzini aniqlamoqchi bo'lgan baytingizni yuboring:")
        p = "Ushbu baytni aruz tizimi bo'yicha tahlil qiling (hijolar, ruknlar, bahr nomi): '{input}'"
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "aruz"))

    elif data == "btn_qadim":
        msg = bot.send_message(cid, "✍️ Qaysi tarixiy yoki arxaik so'z kerak? Yozing:")
        p = "'{input}' so'zini qadimgi turkiy manbalar asosida filologik tahlil qiling."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "qadimgi_til"))

    elif data == "btn_etim":
        msg = bot.send_message(cid, "🔍 Etimologiyasini bilmoqchi bo'lgan so'zingizni yozing:")
        p = "'{input}' so'zining tarixiy ildizi va etimologiyasini tushuntiring."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "etimologiya"))

    elif data == "btn_konspekt":
        msg = bot.send_message(cid, "📋 Qaysi sinf va mavzu bo'yicha dars ishlanmasi kerak? Yozib yuboring:")
        p = "Umumta'lim maktabi uchun '{input}' mavzusida to'liq 45 daqiqalik dars ishlanmasi (konspekt) tuzing."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "konspekt"))

    elif data == "btn_metod":
        msg = bot.send_message(cid, "🎯 Qaysi mavzu uchun interfaol metod kerak? Yozing:")
        p = "'{input}' mavzusi uchun zamonaviy interfaol metod ishlab chiqing."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "metod"))

    elif data == "btn_maqola":
        msg = bot.send_message(cid, "✍️ Ilmiy tadqiqot mavzusini kiriting:")
        p = "OAK talablari asosida '{input}' mavzusida maqola yozish uchun REJA va METODIK KO'RSATMA bering. Tayyor matn bermang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "maqola"))

    elif data == "btn_tezis":
        msg = bot.send_message(cid, "✍️ Tezis mavzusini kiriting:")
        p = "Konferensiya uchun '{input}' mavzusida tezis yozish bo'yicha REJA va YO'RIQNOMA bering. Tayyor matn bermang."
        bot.register_next_step_handler(msg, lambda m: dynamic_ai_delivery(cid, p.format(input=m.text), uid, "tezis"))

    bot.answer_callback_query(call.id)

# --- TESTLARNI GENERATSIYA QILISH ---
def generate_quiz_batch(prompt_spec, count=30):
    models = ["gemini-3.6-flash"]
    for model_name in models:
        for _ in range(3):
            try:
                response = ai_client.models.generate_content(
                    model=model_name,
                    contents=prompt_spec,
                    config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.75)
                )
                raw = response.text.strip()
                if "```json" in raw:
                    raw = raw.split("```json")[1].split("```")[0].strip()
                elif "```" in raw:
                    raw = raw.split("```")[1].split("```")[0].strip()
                questions = json.loads(raw)
                if isinstance(questions, list) and len(questions) >= 10:
                    return questions[:count]
            except Exception:
                time.sleep(2)
    raise Exception("Test savollarini shakllantirishda xatolik yuz berdi.")

def get_themed_bmb_questions(theme_name):
    seed = random.randint(10000, 99999)
    prompt = (
        f"O'zbekiston Respublikasi BMB (DTM) standarti va amaldagi 5-11-sinf Ona tili va adabiyot darsliklari asosida "
        f"aynan '{theme_name}' mavzusi bo'yicha TO'LIQ 30 TA original Quiz test tuzing (Seed #{seed}).\n"
        "Faqat JSON formatida berilsin:\n"
        "[\n"
        "  {\n"
        '    "question": "Savol matni",\n'
        '    "options": ["A", "B", "C", "D"],\n'
        '    "correct_option_id": 0,\n'
        '    "explanation": "Qisqa izoh"\n'
        "  }\n"
        "]"
    )
    return generate_quiz_batch(prompt, 30)

def get_attestation_questions():
    seed = random.randint(10000, 99999)
    prompt = (
        "Maktabgacha va maktab ta'limi vazirligi pedagoglar attestatsiyasi rasmiy spetsifikatsiyasi asosida "
        f"Ona tili va adabiyot fani o'qituvchilari uchun TO'LIQ 40 TA unikal test tuzing (Seed #{seed}).\n"
        "- Y1: 15 ta, Y2: 15 ta, Y3: 10 ta savol.\n"
        "Faqat JSON formatida berilsin."
    )
    return generate_quiz_batch(prompt, 40)

# --- ISHTIROKCHILAR JAVOBLARINI TUTISH ---
@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    poll_id = poll_answer.poll_id
    poll_info = POLL_CORRECT_MAP.get(poll_id)
    if not poll_info:
        return

    chat_id = poll_info["chat_id"]
    correct_opt = poll_info["correct_option_id"]
    chosen_opt = poll_answer.option_ids[0]

    user = poll_answer.user
    u_id = user.id
    u_name = user.first_name or "Ishtirokchi"

    if chat_id in ACTIVE_QUIZ_TRACKER:
        scores = ACTIVE_QUIZ_TRACKER[chat_id]["scores"]
        if u_id not in scores:
            scores[u_id] = {"name": u_name, "correct": 0}
        
        if chosen_opt == correct_opt:
            scores[u_id]["correct"] += 1

# --- TEST JARAYONI VA REYTING LOOP'I ---
def run_interactive_quiz_loop(target_chat_id, questions, duration_per_q, title):
    total_q = len(questions)
    is_channel = str(target_chat_id).startswith("@")
    is_anon = True if is_channel else False

    start_time = time.time()
    ACTIVE_QUIZ_TRACKER[target_chat_id] = {"scores": {}, "total_q": total_q}

    bot.send_message(
        target_chat_id,
        f"🏁 **DIQQAT, {title.upper()} BOSHLANDI!**\n\n"
        f"▫️ Jami savollar: `{total_q} ta`\n"
        f"▫️ Har bir savolga ajratilgan vaqt: `⏳ {duration_per_q} soniya`\n"
        f"▫️ Rasmiy kanal: `{CHANNEL_USERNAME}`\n\n"
        "Har bir to'g'ri javob qayd etiladi va yakunda **REYTING JADVALI** e'lon qilinadi!",
        parse_mode="Markdown"
    )
    time.sleep(2)

    for idx, q_data in enumerate(questions, 1):
        question_text = f"[{idx}/{total_q}] ⏳ {duration_per_q}s | {q_data['question']}"
        if len(question_text) > 295:
            question_text = question_text[:292] + "..."

        options = [str(opt)[:95] for opt in q_data["options"][:4]]
        if len(options) < 2:
            options = ["A varianti", "B varianti"]

        correct_id = int(q_data.get("correct_option_id", 0))
        if correct_id < 0 or correct_id >= len(options):
            correct_id = 0

        explanation = f"{q_data.get('explanation', '')}\n👉 {CHANNEL_USERNAME}"[:195]

        try:
            poll_msg = bot.send_poll(
                chat_id=target_chat_id,
                question=question_text,
                options=options,
                type="quiz",
                correct_option_id=correct_id,
                explanation=explanation,
                is_anonymous=is_anon,
                open_period=duration_per_q
            )
            POLL_CORRECT_MAP[poll_msg.poll.id] = {
                "chat_id": target_chat_id,
                "correct_option_id": correct_id
            }
        except Exception:
            try:
                poll_msg = bot.send_poll(
                    chat_id=target_chat_id,
                    question=question_text,
                    options=options,
                    type="quiz",
                    correct_option_id=correct_id,
                    is_anonymous=True
                )
            except Exception:
                pass

        time.sleep(duration_per_q + 2)

    tracker = ACTIVE_QUIZ_TRACKER.pop(target_chat_id, None)
    duration_total = int(time.time() - start_time)

    if is_channel:
        finish_msg = (
            f"╔════════════════════════════════╗\n"
            f"  🏆 **{title.upper()} YAKUNLANDI!**\n"
            f"╚════════════════════════════════╝\n\n"
            "Kanalda o'tkazilgan test muvaffaqiyatli yakunlandi.\n"
            f"Rasmiy manba: `{CHANNEL_USERNAME}`"
        )
        bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown")
    else:
        scores = tracker["scores"] if tracker else {}
        results = load_data(RESULTS_FILE)
        users = load_data(USERS_FILE)

        if scores:
            for uid, info in scores.items():
                results[str(uid)] = {
                    "name": info["name"],
                    "correct": info["correct"],
                    "duration": duration_total,
                    "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                }
                if str(uid) in users:
                    users[str(uid)]["points"] = users[str(uid)].get("points", 0) + (info["correct"] * 2)

            save_data(RESULTS_FILE, results)
            save_data(USERS_FILE, users)

            sorted_participants = sorted(scores.items(), key=lambda x: x[1]["correct"], reverse=True)
            leaderboard_text = ""
            for rank, (uid, info) in enumerate(sorted_participants, 1):
                medal = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"`#{rank}`"
                perc = round((info["correct"] / total_q) * 100, 1)
                leaderboard_text += f"{medal} **{info['name']}** — `{info['correct']}/{total_q}` to'g'ri (`{perc}%`)\n"

            finish_msg = (
                f"╔════════════════════════════════╗\n"
                f"  🏆 **{title.upper()} REYTINGI**\n"
                f"╚════════════════════════════════╝\n\n"
                f"👥 Jami ishtirokchilar: `{len(sorted_participants)} nafar`\n"
                f"📊 Savollar soni: `{total_q} ta`\n\n"
                "🏅 **ISHTIROKCHILARNING EGALLAGAN O'RINLARI:**\n"
                f"{leaderboard_text}\n"
                "────────────────────────────────\n"
                f"✨ Rasmiy filologik kanalimiz: `{CHANNEL_USERNAME}`"
            )
        else:
            finish_msg = f"╔════════════════════════════════╗\n  🏆 **{title.upper()} YAKUNLANDI!**\n╚════════════════════════════════╝\n\nTest yakunlandi."

        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            ),
            tele_types.InlineKeyboardButton(text="📤 Natijani ulashish", switch_inline_query="Mening test natijam")
        )
        bot.send_message(target_chat_id, finish_msg, parse_mode="Markdown", reply_markup=markup)

# --- 3 KISHILIK SHART (FAQAT GURUH VA KANAL UCHUN) ---
def setup_match_lobby(chat_id, questions, duration_per_q, title):
    match_id = f"m_{int(time.time())}_{random.randint(100, 999)}"
    READY_MATCHES[match_id] = {
        "chat_id": chat_id,
        "questions": questions,
        "duration": duration_per_q,
        "title": title,
        "ready_users": {},
        "started": False
    }

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        tele_types.InlineKeyboardButton(text="✋ Men tayyorman (0/3)", callback_data=f"rdy_{match_id}"),
        tele_types.InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
    )

    announcement = (
        f"╔════════════════════════════════╗\n"
        f"  🧠 **{title.upper()}**\n"
        f"╚════════════════════════════════╝\n\n"
        f"▫️ Savollar soni: `{len(questions)} ta`\n"
        f"▫️ Vaqt me'yori: Har bir savolga `⏳ {duration_per_q} soniya`\n"
        f"▫️ Manzil: `{CHANNEL_USERNAME}`\n\n"
        "⚠️ **Qoida:** Bellashuv boshlanishi uchun kamida **3 nafar ishtirokchi** "
        "«Men tayyorman» tugmasini bosishi lozim!"
    )
    bot.send_message(chat_id, announcement, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("rdy_"))
def callback_match_lobby(call):
    match_id = call.data.replace("rdy_", "")
    m = READY_MATCHES.get(match_id)
    if not m or m["started"]:
        bot.answer_callback_query(call.id, "Test allaqachon boshlangan.", show_alert=True)
        return

    uid = call.from_user.id
    uname = call.from_user.first_name or "Ishtirokchi"

    if uid in m["ready_users"]:
        bot.answer_callback_query(call.id, "Siz tayyorsiz! Boshqalarni kutyapmiz...", show_alert=False)
        return

    m["ready_users"][uid] = uname
    count = len(m["ready_users"])
    bot.answer_callback_query(call.id, f"Qabul qilindi! ({count}/3)")

    if count < 3:
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text=f"✋ Men tayyorman ({count}/3)", callback_data=f"rdy_{match_id}"),
            tele_types.InlineKeyboardButton(text="📢 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_USERNAME.replace('@', '')}")
        )
        try:
            bot.edit_message_reply_markup(chat_id=m["chat_id"], message_id=call.message.message_id, reply_markup=markup)
        except Exception:
            pass
    else:
        m["started"] = True
        names = ", ".join(list(m["ready_users"].values())[:5])
        try:
            bot.edit_message_text(
                chat_id=m["chat_id"],
                message_id=call.message.message_id,
                text=f"🎉 **Yetarli ishtirokchilar yig'ildi! (Tayyorlar: {names})**\n\n🚀 Bellashuv 5 soniyadan so'ng start oladi...",
                parse_mode="Markdown"
            )
        except Exception:
            pass

        time.sleep(5)
        threading.Thread(
            target=run_interactive_quiz_loop,
            args=(m["chat_id"], m["questions"], m["duration"], m["title"]),
            daemon=True
        ).start()

# --- TEST TAYYOR BO'LGANDA YO'NALTIRISH ---
def offer_quiz_dispatch(chat_id, user_id, questions, duration_per_q, title):
    quiz_id = f"qz_{int(time.time())}_{random.randint(100, 999)}"
    PENDING_QUIZZES[quiz_id] = {
        "questions": questions,
        "duration": duration_per_q,
        "title": title
    }

    markup = tele_types.InlineKeyboardMarkup(row_width=1)
    if int(user_id) == int(ADMIN_ID):
        markup.add(
            tele_types.InlineKeyboardButton(text="📢 Kanalga e'lon qilish (@onatilidanyordam)", callback_data=f"act_chan_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="🤖 Botning o'zida ishlash (Yakkaxon - Darhol)", callback_data=f"act_bot_{quiz_id}")
        )
        bot.send_message(
            chat_id,
            f"👑 **Hurmatli Admin!**\n\n**{title}** tayyorlandi. Qayerda o'tkazasiz?",
            parse_mode="Markdown",
            reply_markup=markup
        )
    else:
        markup.add(
            tele_types.InlineKeyboardButton(text="🤖 Botning o'zida yakkaxon ishlash (Darhol)", callback_data=f"act_bot_{quiz_id}"),
            tele_types.InlineKeyboardButton(text="👥 O'z guruhimga tashlash (Bellashuv)", callback_data=f"act_grpinfo_{quiz_id}")
        )
        bot.send_message(
            chat_id,
            f"🎉 **{title}** tayyorlandi!\nQayerda test ishlamoqchisiz?",
            parse_mode="Markdown",
            reply_markup=markup
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith(("act_chan_", "act_bot_", "act_grpinfo_")))
def callback_quiz_routing(call):
    data = call.data
    
    if data.startswith("act_chan_"):
        if int(call.from_user.id) != int(ADMIN_ID):
            bot.answer_callback_query(call.id, "Faqat admin uchun!", show_alert=True)
            return
        quiz_id = data.replace("act_chan_", "")
        q_data = PENDING_QUIZZES.get(quiz_id)
        if not q_data:
            bot.answer_callback_query(call.id, "Test eskirgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Kanalga yuborilmoqda...")
        setup_match_lobby(CHANNEL_USERNAME, q_data["questions"], q_data["duration"], q_data["title"])
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"✅ **{q_data['title']}** rasmiy {CHANNEL_USERNAME} kanaliga e'lon qilindi!\nKanalda 3 kishi «Tayyorman»ni bosgach test boshlanadi."
        )

    elif data.startswith("act_bot_"):
        quiz_id = data.replace("act_bot_", "")
        q_data = PENDING_QUIZZES.get(quiz_id)
        if not q_data:
            bot.answer_callback_query(call.id, "Test eskirgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Test darhol boshlanmoqda!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

        # INDIVIDUAL HOLATDA HECH QANDAY KUTISHLARSIZ DARHOL BOSHLANADI
        threading.Thread(
            target=run_interactive_quiz_loop,
            args=(call.message.chat.id, q_data["questions"], q_data["duration"], q_data["title"]),
            daemon=True
        ).start()

    elif data.startswith("act_grpinfo_"):
        bot.answer_callback_query(call.id)
        info_text = (
            "╭── 👥 **TESTNI GURUHINGIZDA O'TKAZISH TARTIBI** ──╮\n\n"
            "1. Botingizni o'zingizning guruhingizga qo'shing.\n"
            "2. Botga guruhda **Admin** huquqini bering.\n"
            "3. Guruh chatida `/quiz_start` buyrug'ini yuboring.\n"
            "4. 3 kishi «Men tayyorman» tugmasini bosishi bilanoq bellashuv boshlanadi!\n\n"
            f"Rasmiy kanal: `{CHANNEL_USERNAME}`\n"
            "╰──────────────────────────────────────────╯"
        )
        bot.send_message(call.message.chat.id, info_text, parse_mode="Markdown")

@bot.message_handler(commands=['quiz_start'])
def cmd_quiz_start_group(message):
    chat_type = message.chat.type
    if chat_type in ['group', 'supergroup']:
        bot.reply_to(message, "⏳ *Guruh uchun 30 talik test paketi shakllanmoqda...*", parse_mode="Markdown")
        try:
            bmb_num = get_next_quiz_number("bmb_30")
            quiz_title = f"№{bmb_num} BMB 30 talik test (Guruh Bellashuvi)"
            questions = get_themed_bmb_questions("5-11-sinf barcha darsliklari")
            setup_match_lobby(message.chat.id, questions, duration_per_q=30, title=quiz_title)
        except Exception as e:
            bot.reply_to(message, f"❌ Xatolik yuz berdi: {e}")
    else:
        bot.reply_to(message, "Ushbu buyruq faqat guruhlarda ishlaydi.")

# --- ADMIN PANEL VA FOYDALANUVCHILAR RO'YXATI ---
def get_users_page_markup(page=0, per_page=8):
    users = load_data(USERS_FILE)
    items = list(users.items())
    total_users = len(items)
    total_pages = max(1, (total_users + per_page - 1) // per_page)
    
    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total_users)
    current_items = items[start_idx:end_idx]

    active_count = sum(1 for _, u in items if u.get("status") != "blocked")
    blocked_count = total_users - active_count

    text = f"👥 **BOT FOYDALANUVCHILARI**\n▫️ Jami: `{total_users}` | Faol: `{active_count}` | ❌ To'xtatgan: `{blocked_count}`\n📄 Sahifa: `{page + 1}/{total_pages}`\n\n"

    markup = tele_types.InlineKeyboardMarkup(row_width=2)
    for idx, (uid, data) in enumerate(current_items, start=start_idx + 1):
        name = data.get("first_name", "Foydalanuvchi")
        uname = f"@{data['username']}" if data.get("username") else "usernamesiz"
        st = "🟢" if data.get("status") != "blocked" else "🔴"
        streak = data.get("streak", 1)
        points = data.get("points", 0)
        
        text += f"`{idx}.` {st} **{name}** ({uname})\n    └ ID: `{uid}` • 🔥 {streak} kun • `{points} ball`\n"
        btn_label = f"💬 {name[:12]}..." if len(name) > 12 else f"💬 {name}"
        markup.add(tele_types.InlineKeyboardButton(text=btn_label, callback_data=f"sendpm_{uid}"))

    nav_btns = []
    if page > 0:
        nav_btns.append(tele_types.InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"usrpage_{page - 1}"))
    if page + 1 < total_pages:
        nav_btns.append(tele_types.InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"usrpage_{page + 1}"))
    if nav_btns:
        markup.row(*nav_btns)

    markup.add(
        tele_types.InlineKeyboardButton(text="📢 Hammaga umumiy xabar yo'llash", callback_data="admin_broadcast_start"),
        tele_types.InlineKeyboardButton(text="👤 ID orqali individual yozish", callback_data="admin_pm_manual"),
        tele_types.InlineKeyboardButton(text="🔙 Boshqaruv menyusi", callback_data="admin_back_to_panel")
    )
    return text, markup

@bot.callback_query_handler(func=lambda call: call.data.startswith(("usrpage_", "sendpm_", "admin_broadcast_start", "admin_pm_manual", "admin_back_to_panel", "admin_view_users")))
def callback_admin_user_management(call):
    if int(call.from_user.id) != int(ADMIN_ID):
        bot.answer_callback_query(call.id, "Faqat admin uchun!", show_alert=True)
        return

    data = call.data
    cid = call.message.chat.id
    mid = call.message.message_id

    if data == "admin_view_users":
        text, markup = get_users_page_markup(page=0)
        bot.edit_message_text(chat_id=cid, message_id=mid, text=text, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("usrpage_"):
        page = int(data.replace("usrpage_", ""))
        text, markup = get_users_page_markup(page=page)
        bot.edit_message_text(chat_id=cid, message_id=mid, text=text, parse_mode="Markdown", reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("sendpm_"):
        target_uid = data.replace("sendpm_", "")
        users = load_data(USERS_FILE)
        u_info = users.get(target_uid, {})
        u_name = u_info.get("first_name", "Foydalanuvchi")

        bot.answer_callback_query(call.id)
        msg = bot.send_message(cid, f"✍️ **{u_name}** (`ID: {target_uid}`) ga xabaringizni yozing:\n*(Bekor qilish: `/cancel`)*", parse_mode="Markdown")
        def forward_pm_text(m):
            if m.text.strip() == "/cancel":
                bot.send_message(cid, "❌ Bekor qilindi.")
                return
            try:
                bot.send_message(target_uid, f"📬 **Administrator xabarnomasi:**\n\n{m.text}\n\n🏛 **Kanal:** `{CHANNEL_USERNAME}`", parse_mode="Markdown")
                bot.send_message(cid, f"✅ Xabar yetkazildi: `{target_uid}` ({u_name})", parse_mode="Markdown")
            except Exception as e:
                if "blocked by the user" in str(e):
                    users_db = load_data(USERS_FILE)
                    if str(target_uid) in users_db:
                        users_db[str(target_uid)]["status"] = "blocked"
                        save_data(USERS_FILE, users_db)
                bot.send_message(cid, "❌ Foydalanuvchi botni bloklagan.")
        bot.register_next_step_handler(msg, forward_pm_text)

    elif data == "admin_pm_manual":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(cid, "👤 Foydalanuvchining **Telegram ID raqamini** kiriting:")
        def ask_id_step(m_id):
            target_id = m_id.text.strip()
            if not target_id.isdigit():
                bot.send_message(cid, "❌ Xato! ID faqat sonlardan iborat bo'ladi.")
                return
            msg_txt = bot.send_message(cid, f"✍️ `ID: {target_id}` ga xabaringizni yozing:")
            def send_direct_msg(m_text):
                try:
                    bot.send_message(target_id, f"📬 **Administrator xabarnomasi:**\n\n{m_text.text}\n\n🏛 **Kanal:** `{CHANNEL_USERNAME}`", parse_mode="Markdown")
                    bot.send_message(cid, f"✅ Xabar yetkazildi (`{target_id}`)", parse_mode="Markdown")
                except Exception:
                    bot.send_message(cid, "❌ Foydalanuvchi botni bloklagan.")
            bot.register_next_step_handler(msg_txt, send_direct_msg)
        bot.register_next_step_handler(msg, ask_id_step)

    elif data == "admin_broadcast_start":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(cid, "📢 **Barcha a'zolarga umumiy xabar (Broadcast):**\n\nXabar matnini kiriting:\n*(Bekor qilish: `/cancel`)*", parse_mode="Markdown")
        def broadcast_step(m):
            if m.text.strip() == "/cancel":
                bot.send_message(cid, "❌ Bekor qilindi.")
                return
            users = load_data(USERS_FILE)
            success, blocked = 0, 0
            bot.send_message(cid, f"🚀 {len(users)} ta a'zoga tarqatish boshlandi...")
            for uid_key in list(users.keys()):
                try:
                    bot.send_message(uid_key, f"📢 **Umumiy E'lon:**\n\n{m.text}\n\n🏛 **Kanal:** `{CHANNEL_USERNAME}`", parse_mode="Markdown")
                    success += 1
                    users[uid_key]["status"] = "active"
                    time.sleep(0.04)
                except Exception as ex:
                    if "blocked by the user" in str(ex):
                        users[uid_key]["status"] = "blocked"
                        blocked += 1
            save_data(USERS_FILE, users)
            bot.send_message(cid, f"✅ **Tarqatish yakunlandi!**\n\n▫️ Yetkazildi: `{success} ta`\n▫️ Bloklaganlar: `{blocked} ta`", parse_mode="Markdown")
        bot.register_next_step_handler(msg, broadcast_step)

    elif data == "admin_back_to_panel":
        users = load_data(USERS_FILE)
        results = load_data(RESULTS_FILE)
        ch_count = bot.get_chat_member_count(CHANNEL_USERNAME)
        active_u = sum(1 for _, u in users.items() if u.get("status") != "blocked")
        blocked_u = len(users) - active_u

        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="👥 Foydalanuvchilar ro'yxatini ko'rish", callback_data="admin_view_users"),
            tele_types.InlineKeyboardButton(text="📢 Barcha a'zolarga umumiy xabar yo'llash", callback_data="admin_broadcast_start"),
            tele_types.InlineKeyboardButton(text="👤 Individual xabar yuborish", callback_data="admin_pm_manual"),
            tele_types.InlineKeyboardButton(
                text="🏆 Jonli Reyting Doskasi (Mini-App)", 
                web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")
            )
        )
        bot.edit_message_text(
            chat_id=cid,
            message_id=mid,
            text=f"📊 **BOSHQARUV PANELI (ADMIN):**\n\n▫️ Jami a'zolar: `{len(users)} ta`\n▫️ Faol a'zolar: `{active_u} ta`\n▫️ To'xtatganlar: `{blocked_u} ta`\n▫️ Kanal a'zolari: `{ch_count} ta`",
            parse_mode="Markdown",
            reply_markup=markup
        )
        bot.answer_callback_query(call.id)

# --- ADMIN KUN HIKMATI VA MOTIVATSIYA ---
def get_verified_didactic_content(content_type="hikmat"):
    chosen_epoch = random.choice(HISTORICAL_EPOCHS)
    seed = random.randint(1000, 99999)
    if content_type == "hikmat":
        prompt = f"O'zbek adabiyoti bo'yicha {chosen_epoch['epoch']} davriga oid 1 ta didaktik hikmatni aniq manbasi bilan keltiring (Seed #{seed}). Diniy va siyosiy mavzulardan chetlashing.\n\nFormat:\n🏛 **Davr:** {chosen_epoch['epoch']}\n\n[HIKMAT MATNI]\n\n📚 Aniq manba: [Muallif, asar nomi]"
    else:
        prompt = f"O'zbek ma'rifati bo'yicha {chosen_epoch['epoch']} davri allomalaridan yoshlarni ilmga chorlovchi 1 ta motivatsiya keltiring (Seed #{seed}). Diniy va siyosiy mavzulardan chetlashing.\n\nFormat:\n🏛 **Davr:** {chosen_epoch['epoch']}\n\n[MOTIVATSIYA MATNI]\n\n📚 Aniq manba: [Muallif, asar nomi]"
    
    response = ai_client.models.generate_content(
        model="gemini-3.6-flash",
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.7)
    )
    return response.text.strip()

@bot.callback_query_handler(func=lambda call: call.data.startswith(("send_chan_", "cancel_", "pub_")))
def callback_admin_publish(call):
    if int(call.from_user.id) != int(ADMIN_ID):
        return
    data = call.data
    if data.startswith("pub_"):
        post_id = data.replace("pub_", "")
        text_data = ADMIN_POST_STORAGE.get(post_id)
        if text_data:
            clean_text = text_data.split("📚 Aniq manba:")[0].strip()
            channel_post = f"{clean_text}\n\n───────────────\n🌟 **Rasmiy kanal:** `{CHANNEL_USERNAME}`"
            bot.send_message(CHANNEL_USERNAME, channel_post, parse_mode="Markdown")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"{call.message.text}\n\n✅ **Kanalga manbasiz joylandi!**")
            bot.answer_callback_query(call.id, "Kanalga joylandi!")
    elif data.startswith("send_chan_"):
        post_id = data.replace("send_chan_", "")
        content = ADMIN_POST_STORAGE.get(post_id)
        if content:
            bot.send_message(CHANNEL_USERNAME, content, parse_mode="Markdown")
            bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"{call.message.text}\n\n✅ **Kanalga e'lon qilindi!**")
            bot.answer_callback_query(call.id, "Kanalga joylandi!")
    elif data.startswith("cancel_"):
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Bekor qilindi.")

# --- KANALGA AVTO-POSTING (08:30 VA 20:30) ---
def auto_poster_loop():
    tz = pytz.timezone('Asia/Tashkent')
    sent_flags = {"08:30": False, "20:30": False}
    while True:
        try:
            now = datetime.now(tz)
            current_time = now.strftime("%H:%M")
            if current_time == "00:01":
                for k in sent_flags:
                    sent_flags[k] = False

            if current_time == "08:30" and not sent_flags["08:30"]:
                hikmat_full = get_verified_didactic_content("hikmat")
                clean_text = hikmat_full.split("📚 Aniq manba:")[0].strip()
                bot.send_message(CHANNEL_USERNAME, f"☀️ **TONGGI HIKMAT**\n\n{clean_text}\n\n───────────────\n🌟 `{CHANNEL_USERNAME}`", parse_mode="Markdown")
                sent_flags["08:30"] = True

            elif current_time == "20:30" and not sent_flags["20:30"]:
                bot.send_message(CHANNEL_USERNAME, "🧠 **KECHKI INTELLEKT: BMB TEST SINOVI**")
                for _ in range(3):
                    try:
                        q_obj = json.loads(ai_client.models.generate_content(
                            model="gemini-3.6-flash",
                            contents="BMB standarti bo'yicha 5-11-sinf Ona tilidan 1 ta Quiz test tuzing. Faqat JSON formatida: {\"question\":\"...\",\"options\":[\"A\",\"B\",\"C\",\"D\"],\"correct_option_id\":0,\"explanation\":\"...\"}",
                            config=types.GenerateContentConfig(system_instruction=SYSTEM_INSTRUCTION, temperature=0.8)
                        ).text.strip().replace("```json", "").replace("```", ""))
                        bot.send_poll(
                            chat_id=CHANNEL_USERNAME,
                            question=f"⏳ {q_obj['question'][:280]}",
                            options=[opt[:95] for opt in q_obj["options"][:4]],
                            type="quiz",
                            correct_option_id=q_obj["correct_option_id"],
                            explanation=f"{q_obj.get('explanation', '')}\n👉 {CHANNEL_USERNAME}"[:190],
                            is_anonymous=True
                        )
                        time.sleep(3)
                    except Exception:
                        pass
                sent_flags["20:30"] = True
            time.sleep(30)
        except Exception:
            time.sleep(30)

threading.Thread(target=auto_poster_loop, daemon=True).start()

# --- START BUYRUG'I ---
@bot.message_handler(commands=['start'])
def send_welcome(message):
    streak, points, streak_broken = update_user_streak(message.from_user)
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    streak_msg = "\n⚠️ *Siz kecha kirmaganingiz sababli olovli seriya qaytadan boshlandi!*\n" if streak_broken else f"\n🔥 **Olovli seriya:** `{streak} kun davom etmoqda!` (+25 XP)\n"
    user_name = message.from_user.first_name or "Foydalanuvchi"
    text = (
        f"╭──── ✨ **Assalomu alaykum, {user_name}!** ────╮\n\n"
        f"🏛 **AI TILSHUNOS & METODIST (v11.0)** portaliga xush kelibsiz!\n"
        f"{streak_msg}\n"
        "Quyidagi asosiy yo'nalishlardan birini tanlang:\n\n"
        "🎓 **Talabalar uchun:** Mumtoz meros, aruz, qadimgi til va etimologiya\n"
        "👨‍🏫 **O'qituvchilar uchun:** Konspektlar, metodlar va Attestatsiya testlari\n"
        "🎒 **Abituriyentlar uchun:** 🎖 Milliy sertifikat (Esse markazi), BMB va Mavzuli testlar\n"
        "🔬 **Ilmiy izlanuvchilar uchun:** OAK maqola va tezis loyihalash\n\n"
        "👇 *Yo'nalishingizni tanlang:* \n"
        "╰─────────────────────────────────────╯"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_main_menu(message.from_user.id))

@bot.callback_query_handler(func=lambda call: call.data in ["check_sub"])
def callback_check_sub(call):
    update_user_streak(call.from_user)
    if is_subscribed(call.from_user.id):
        bot.answer_callback_query(call.id, "🎉 Obuna tasdiqlandi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        send_welcome(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ Siz hali kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- ASOSIY MENYU XABARLARI ISHLOVCHISI ---
@bot.message_handler(func=lambda msg: True)
def handle_all_messages(message):
    update_user_streak(message.from_user)
    if not is_subscribed(message.from_user.id):
        send_subscription_prompt(message.chat.id)
        return

    text = message.text
    u_id = message.from_user.id
    is_admin = (int(u_id) == int(ADMIN_ID))

    if text == "🔙 Asosiy menyu":
        bot.send_message(message.chat.id, "📋 Asosiy toifalardan birini tanlang:", reply_markup=get_main_menu(u_id))
        return
    elif text == "🎒 Abituriyentlar uchun":
        send_section_card(message.chat.id, "abituriyent")
    elif text == "🎓 Talabalar uchun":
        send_section_card(message.chat.id, "talaba")
    elif text == "👨‍🏫 O'qituvchilar uchun":
        send_section_card(message.chat.id, "oqituvchi")
    elif text == "🔬 Ilmiy izlanuvchilar uchun":
        send_section_card(message.chat.id, "izlanuvchi")
    elif text == "👤 Shaxsiy kabinet":
        users = load_data(USERS_FILE)
        results = load_data(RESULTS_FILE)
        u_data = users.get(str(u_id), {})
        best_correct = results.get(str(u_id), {}).get("correct", 0)
        profile_text = (
            f"👤 **SHAXSIY KABINET**\n\n"
            f"▫️ Ism: {message.from_user.first_name}\n"
            f"▫️ ID: `{u_id}`\n"
            f"▫️ Olovli seriya: 🔥 `{u_data.get('streak', 1)} kun`\n"
            f"▫️ To'plangan ballar: `{u_data.get('points', 0)} XP`\n"
            f"▫️ BMB testdagi eng yaxshi natija: `{best_correct}/30 to'g'ri`"
        )
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(tele_types.InlineKeyboardButton(text="🏆 Jonli Reyting Doskasi (Mini-App)", web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")))
        bot.send_message(message.chat.id, profile_text, parse_mode="Markdown", reply_markup=markup)
    elif text == "🏆 Jonli Reyting Doskasi":
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(tele_types.InlineKeyboardButton(text="🏆 Jonli Reyting Doskasi (Mini-App)", web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard")))
        bot.send_message(message.chat.id, "🏆 Quyidagi havola orqali respublika reyting doskasini ko'rishingiz mumkin:", reply_markup=markup)
    elif text == "📊 Boshqaruv & Statistika" and is_admin:
        users = load_data(USERS_FILE)
        results = load_data(RESULTS_FILE)
        ch_count = bot.get_chat_member_count(CHANNEL_USERNAME)
        active_u = sum(1 for _, u in users.items() if u.get("status") != "blocked")
        blocked_u = len(users) - active_u
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            tele_types.InlineKeyboardButton(text="👥 Foydalanuvchilar ro'yxatini ko'rish", callback_data="admin_view_users"),
            tele_types.InlineKeyboardButton(text="📢 Barcha a'zolarga umumiy xabar yo'llash", callback_data="admin_broadcast_start"),
            tele_types.InlineKeyboardButton(text="👤 Individual xabar yuborish", callback_data="admin_pm_manual"),
            tele_types.InlineKeyboardButton(text="🏆 Jonli Reyting Doskasi (Mini-App)", web_app=tele_types.WebAppInfo(url=f"{RENDER_APP_URL}/leaderboard"))
        )
        bot.send_message(message.chat.id, f"📊 **BOSHQARUV PANELI (ADMIN):**\n\n▫️ Jami: `{len(users)}` | Faol: `{active_u}` | Bloklagan: `{blocked_u}`\n▫️ Test topshirganlar: `{len(results)} ta`\n▫️ Kanal a'zolari: `{ch_count} ta`", parse_mode="Markdown", reply_markup=markup)
    elif text == "☀️ Kun hikmati (Admin)" and is_admin:
        hikmat_full = get_verified_didactic_content("hikmat")
        p_id = f"hik_{int(time.time())}"
        ADMIN_POST_STORAGE[p_id] = hikmat_full
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(tele_types.InlineKeyboardButton(text="📢 Kanalga joylash (Manbasiz)", callback_data=f"pub_{p_id}"), tele_types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{p_id}"))
        bot.send_message(message.chat.id, f"☀️ **KUN HIKMATI (ADMIN TEKSHIRUVI):**\n\n{hikmat_full}", parse_mode="Markdown", reply_markup=markup)
    elif text == "⚡️ Motivatsiya (Admin)" and is_admin:
        motiv_full = get_verified_didactic_content("motiv")
        p_id = f"mot_{int(time.time())}"
        ADMIN_POST_STORAGE[p_id] = motiv_full
        markup = tele_types.InlineKeyboardMarkup(row_width=1)
        markup.add(tele_types.InlineKeyboardButton(text="📢 Kanalga joylash (Manbasiz)", callback_data=f"pub_{p_id}"), tele_types.InlineKeyboardButton(text="❌ Bekor qilish", callback_data=f"cancel_{p_id}"))
        bot.send_message(message.chat.id, f"⚡️ **MOTIVATSIYA (ADMIN TEKSHIRUVI):**\n\n{motiv_full}", parse_mode="Markdown", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "Iltimos, menyu tugmalaridan birini tanlang:", reply_markup=get_main_menu(u_id))

print("AI Tilshunos v11.0 (Milliy Sertifikat Suite) faol ishga tushdi...")
bot.infinity_polling()
