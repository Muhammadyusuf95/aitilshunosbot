"""Statik kontent: esse mavzulari, mavzular katalogi, AI asboblar tavsifi, namunaviy matnlar."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from data.essays import SAMPLE_ESSAYS
except Exception:  # pragma: no cover
    SAMPLE_ESSAYS = []

CERT_ESSAY_TOPICS = [
    "Aksariyat maktab bitiruvchilari oliy ta'limni talab etmaydigan zamonaviy kasblarni egallashga qiziqish bildirishsa, ayrimlar zamonaviy kasblar insonga butun umrlik faoliyat bo'lib qolishiga ishonishmaydi.",
    "Ba'zilar bolaga mukammal bilim berish uchun uni xususiy maktabda o'qitish kerak deb hisoblashsa, ayrimlar davlat maktabida ham mukammal bilim olish mumkin deb bilishadi.",
    "Ayrimlar turli shoular va yutuqli oʻyinlar odamlarning bir-biriga bo'lgan ishonchini soʻndiradi degan fikrda, ba'zilar esa bunday ko'ngilochar oʻyinlarning afzalliklari haqida gapirishadi.",
    "Ayrimlar chet tilini o'rganish madaniylikning bir belgisi deb bilsalar, ba'zilar o'zga tilini bilish moddiy hayotni ta'minlaydi deydilar.",
    "Hozirgi kunda ayrim insonlar reklamalarga ma'lumot ulashishning eng samarali usuli deb qarasa, ayrimlar bu borada cheklovlar qo'yish kerak deb bilishadi.",
    "Ayrimlar ko'p farzandlilik davlat va jamiyat taraqqiyoti uchun foyda keltiradi deb bilsa, ayrimlar oilada farzand tarbiyasiga e'tibor yetarli bo'lmaydi deb hisoblashadi.",
    "Ko'p qavatli uylar qurilishining avj olishi shahar arxitekturasi va dizayniga yangicha tus beradi, biroq koʻp aholi bunday uylar o'rniga xonadon yoki manzarali yer maydoni qurilishini ma'qul topadi.",
    "Ba'zilar kredit yillar davomida ushalmagan orzularni amalga oshirishning qulay yo'li deb hisoblashadi, ayrimlari esa kredit ortiqcha xarajati va moliyaviy holatni qiyinlashtiradi degan fikrda.",
    "Bugungi kunda sodir bo'layotgan jinoyatlar OAV, internet tarmoqlari orqali ommaga taqdim etilmoqda. Oshkora ko'rsatilishi kimlar uchundir jinoyatga yo'l ochib berishi mumkin deb qaralsa, baʼzilar oshkor ko'rsatish tarafdori.",
    "Ayrimlar oilaviy muammolar aks etgan videolavhalarning ijtimoiy tarmoqlarda tarqalishi jamiyat ma'naviyatiga va ruhiyatiga salbiy ta'sir koʻrsatadi deb bilishsa, ayrimlar aksincha fikrda.",
    "Ayrimlar yaxshi yashash uchun bitta kasbning mohir ustasi bo'lish kerak deb bilishsa, ba'zilar bir necha kasbning egasi bo'lish foydaliroq deb hisoblaydilar.",
    "Sun'iy intellektning insoniyat hayotiga ijobiy va salbiy ta'sirlari.",
    "Plastik qadoqdagi suv yoki vodoprovod suvi iste'moli: afzallik va kamchiliklar.",
    "O'qitishda milliy usullarni yanada rivojlantirish muhimmi yoki chet el tajribasini qo'llashmi?",
    "Anʼanaviy to'ylar xorijiy to'ylar kabi ixcham va zamonaviy tarzda o'tkazilishiga munosabat.",
    "Zamonaviy kitobxonlar audio kitoblarning afzalligini ta'kidlashmoqda, ammo ba'zilar bu fikrga qarshi.",
    "Psixologlar tarbiyada erkinlik muhimligini taʼkidlashmoqda, ammo ba'zilar erkinlik salbiy oqibatlarga olib keladi degan fikrda.",
    "Ba'zilar inson faoliyati tufayli yer shari zararlanib borayotganini ta'kidlashmoqda, ayrimlar esa uni yashash uchun yaxshiroq joyga aylantiradi deb o'ylaydi.",
    "Ba'zilar ta'lim jarayonida mehnat faoliyati bilan shug'ullansa tajriba oshadi deyishsa, ayrimlar faqat bilim olish muhimligini ta'kidlashadi.",
]

# key -> (menyu nomi, AI uchun yo'nalish, baza.json 'bolim' nomlari)
THEME_CATALOG = {
    "cat_fonetika": ("🗣 Fonetika, orfoepiya, imlo",
                     "Fonetika: unli va undoshlar tasnifi, tovush o'zgarishlari, bo'g'in, urg'u hamda rasmiy imlo mezonlari",
                     ["Imlo", "Fonetika", "Punktuatsiya"]),
    "cat_leksika": ("📖 Leksikologiya, frazeologiya",
                    "Leksikologiya: o'z va o'zlashgan qatlam, ma'nodosh, shakldosh, zid ma'noli so'zlar, paronimlar va frazeologik iboralar",
                    ["Leksikologiya", "Ma'no ko'chishi", "Uslubiyat"]),
    "cat_morf_mustaqil": ("🧩 Morfologiya: mustaqil so'zlar",
                          "Mustaqil so'z turkumlari: ot, sifat, son, olmosh, ravish hamda fe'l nisbatlari va zamonlari",
                          ["Morfologiya", "Morfologiyaga kirish", "Fe'l: Zamon", "Fe'l zamonlari", "Fe'l nisbatlari",
                           "Fe'l: Shaxs-son", "Sifat", "Ravish", "Morfemika"]),
    "cat_morf_yordamchi": ("🔗 Morfologiya: yordamchi so'zlar",
                           "Yordamchi so'zlar (ko'makchi, bog'lovchi, yuklama), modal so'zlar, taqlidlar va undovlar uslubiyati hamda imlosi",
                           ["Ko'makchi", "Modal so'zlar", "Yordamchi so'zlar"]),
    "cat_sintaksis": ("📐 Sintaksis va punktuatsiya",
                      "Sintaksis: so'z birikmasi, gap bo'laklari, uyushiq va ajratilgan bo'laklar, qo'shma gaplar va tinish belgilari",
                      ["Sintaksis", "Punktuatsiya"]),
    "cat_mumtoz": ("📜 Mumtoz adabiyot",
                   "Mumtoz adabiyot: Alisher Navoiy va Bobur ijodi, aruz, mumtoz she'riy janrlar va badiiy san'atlar",
                   ["Adabiyot", "Adabiyot va uslubiyat"]),
    "cat_jadid": ("💡 Jadid va XX asr adabiyoti",
                  "Jadid va XX asr adabiyoti: Behbudiy, Avloniy, Fitrat, Cho'lpon, Qodiriy, Oybek, G'afur G'ulom asarlari va qahramonlari",
                  ["Adabiyot"]),
    "cat_til_tarix": ("🌍 Til tarixi va til qonuni",
                      "Til ijtimoiy hodisa sifatida, turkiy tillar oilasi, jahon tillari va davlat tili haqidagi qonun asoslari",
                      ["Til – ijtimoiy hodisa", "Turkiy tillar oilasi", "Til oilalari", "Xalqaro tillar",
                       "Davlat tili haqidagi qonun", "Matn bilan ishlash"]),
}

HISTORICAL_EPOCHS = [
    ("Qadimgi va ilk o'rta asrlar turkiy yozma obidalari (XI-XII asrlar)",
     "Yusuf Xos Hojibning 'Qutadg'u bilig', Mahmud Koshg'ariyning 'Devonu lug'atit turk', Ahmad Yugnakiyning 'Hibat ul-haqoyiq'"),
    ("Temuriylar davri va Oltin asr mumtoz adabiyoti (XV-XVI asrlar)",
     "Alisher Navoiy ('Mahbub ul-qulub', 'Nazm ul-javohir', 'Xamsa'), Zahiriddin Muhammad Bobur ('Boburnoma'), Lutfiy"),
    ("XVII-XIX asrlar o'zbek mumtoz adabiyoti va ma'rifati",
     "Boborahim Mashrab, Turdi Forog'iy, Muhammadrizo Ogahiy, Munis Xorazmiy, Nodirabegim"),
    ("XX asr boshi Jadid ma'rifatparvarlik harakati davri",
     "Mahmudxo'ja Behbudiy, Abdulla Avloniy ('Turkiy Guliston yoxud axloq'), Munavvarqori, Fitrat, Cho'lpon"),
    ("XX asr o'zbek adabiyoti durdonalari",
     "Abdulla Qodiriy ('O'tkan kunlar'), Oybek, G'afur G'ulom, Erkin Vohidov, Abdulla Oripov, O'tkir Hoshimov"),
]

# ---------------------------------------------------------------------------------------------
# AI asboblari: kalit -> tavsif. `prompt` ichidagi {input} foydalanuvchi matni bilan almashtiriladi.
# ---------------------------------------------------------------------------------------------
TOOLS = {
    "gazal": dict(
        title="📜 G'azal tahlili", ask="Badiiy tahlil qilmoqchi bo'lgan mumtoz bayt yoki g'azal parchasini yuboring:",
        prompt=("Quyidagi mumtoz bayt/g'azal parchasini badiiy tahlil qiling:\n{input}\n\n"
                "Tuzilma: ## Nasriy mazmuni, ## Qiyin so'zlar sharhi (eskirgan so'zlar ma'nosi), "
                "## Badiiy san'atlar (tashbeh, istiora, tanosub, talmeh, tazod va h.k. — har birini matndan misol bilan), "
                "## Mavzu va g'oya. Muallifni faqat aniq bilsangiz ayting."),
        tag="gazal"),
    "aruz": dict(
        title="📐 Aruz hisoblagich", ask="Aruz vaznini aniqlamoqchi bo'lgan baytni yuboring:",
        prompt=("Quyidagi baytning aruz vaznini aniqlang:\n{input}\n\n"
                "1) Baytni hijolarga bo'ling; 2) har hijoni cho'ziq (–) yoki qisqa (U) belgisi bilan yozing; "
                "3) bahr nomini va rukn (taf'ila) tizimini ayting; 4) har misra uchun vazn mosligini tekshiring. "
                "Natijaga to'liq ishonchingiz bo'lmasa, 'Taxminiy' deb belgilab, sababini yozing."),
        tag="aruz"),
    "qadim": dict(
        title="🏛 Qadimgi turkiy so'zlar", ask="Qaysi tarixiy yoki arxaik so'z/iborani tahlil qilay? Yozing:",
        prompt=("'{input}' so'zi/iborasini qadimgi turkiy manbalar (Orxon-Enisey bitiklari, 'Devonu lug'atit turk', "
                "'Qutadg'u bilig') nuqtai nazaridan tahlil qiling: qadimgi shakli, ma'nosi, zamonaviy o'zbek tilidagi "
                "muqobili va tovush o'zgarishlari. Aniq bo'lmagan joylarni 'ehtimol' deb belgilang."),
        tag="qadimgi_til"),
    "etim": dict(
        title="🔍 So'z etimologiyasi", ask="Etimologiyasini bilmoqchi bo'lgan so'zni yozing:",
        prompt=("'{input}' so'zining etimologiyasini tushuntiring: kelib chiqishi (qaysi tildan), ildiz va qo'shimchalari, "
                "tarixiy ma'no o'zgarishi, qardosh tillardagi shakllari. Rahmatullayev lug'ati yondashuviga tayaning; "
                "bahsli yoki noaniq joylarni ochiq ayting."),
        tag="etimologiya"),
    "asar": dict(
        title="📚 Asar tahlili rejasi", ask="Asar nomi va muallifini (yoki qahramon nomini) yozing:",
        prompt=("'{input}' asarini maktab/BMB talablari bo'yicha tahlil qilish rejasini tuzing: ## Muallif va davr, "
                "## Mavzu va g'oya, ## Kompozitsiya va syujet, ## Asosiy qahramonlar xarakteri, ## Badiiy tasvir vositalari, "
                "## Esse yoki og'zaki javob uchun tayyor 5 ta fikr. Asar tafsilotini bilmasangiz, to'qimang."),
        tag="asar"),
    "konspekt": dict(
        title="📋 45 daqiqalik dars ishlanmasi", ask="Qaysi sinf va mavzu bo'yicha dars ishlanmasi kerak? Yozing:",
        prompt=("'{input}' bo'yicha umumta'lim maktabi uchun 45 daqiqalik dars ishlanmasi tuzing: "
                "## Maqsad (ta'limiy, tarbiyaviy, rivojlantiruvchi), ## Kutiladigan natijalar, ## Jihozlar, "
                "## Dars bosqichlari (har biriga daqiqa ajratilgan), ## Interfaol metod, "
                "## Savol-topshiriqlar (Blum taksonomiyasi bo'yicha 3 daraja), ## Uyga vazifa, ## Baholash mezoni."),
        tag="konspekt"),
    "metod": dict(
        title="🎯 Interfaol metod", ask="Qaysi mavzu uchun interfaol metod kerak? Yozing:",
        prompt=("'{input}' mavzusi uchun 3 ta zamonaviy interfaol metod (masalan: Venn diagrammasi, FSMU, Klaster, "
                "Insert, Bumerang) tavsiya qiling. Har biri uchun: maqsad, bosqichma-bosqich o'tkazish, vaqt va tayyor misol."),
        tag="metod"),
    "rubrika": dict(
        title="🗂 Baholash rubrikasi", ask="Qaysi topshiriq yoki mavzu uchun baholash rubrikasi kerak? Yozing:",
        prompt=("'{input}' bo'yicha o'quvchilar ishini baholash rubrikasini tuzing: 4 ta mezon, har biri uchun 4 daraja "
                "(a'lo, yaxshi, qoniqarli, past) va aniq ballar. Ro'yxat ko'rinishida bering."),
        tag="rubrika"),
    "izoh": dict(
        title="📖 So'z izohi (O'TIL) va imlo", ask="Izohini yoki imlosini bilmoqchi bo'lgan so'zni yozing:",
        prompt=("'{input}' so'zini o'zbek tilining izohli lug'ati va amaldagi imlo qoidalari asosida sharhlang: "
                "so'z turkumi, ma'nolari, qo'llanishi, to'g'ri imlosi (birga/ajratib/chiziqcha bilan), "
                "sinonim va antonimlari, 2 ta misol gap."),
        tag="izoh_imlo"),
    "imlo": dict(
        title="✅ Imlo va uslub tekshiruvi", ask="Tekshirilishi kerak bo'lgan matnni yuboring (matn yoki rasm sifatida):",
        prompt=("Quyidagi matnni imlo, punktuatsiya va uslub jihatidan tekshiring:\n{input}\n\n"
                "Tuzilma: ## Tuzatilgan matn, ## Xatolar ro'yxati (xato → to'g'risi → qisqa qoida), ## Uslubiy tavsiya. "
                "Faqat haqiqiy xatolarni belgilang; to'g'ri yozilgan joyni 'tuzatmang'."),
        tag="imlo", photo=True),
    "maqola": dict(
        title="📑 Ilmiy maqola konstruktori (OAK)", ask="Ilmiy tadqiqot mavzusini kiriting:",
        prompt=("OAK talablari asosida '{input}' mavzusida ilmiy maqola uchun REJA va USLUBIY KO'RSATMA bering: "
                "sarlavha, annotatsiya, kalit so'zlar, IMRAD bo'limlari (har birida nima yoziladi), adabiyotlar. "
                "Tayyor maqola matnini yozmang."),
        tag="maqola"),
    "tezis": dict(
        title="📄 Konferensiya tezisi", ask="Tezis mavzusini kiriting:",
        prompt=("Konferensiya uchun '{input}' mavzusida tezis yozish bo'yicha YO'RIQNOMA bering: tuzilma, hajm (1-2 bet), "
                "har bo'lim uchun namunaviy iboralar. Tayyor tezis matnini yozmang."),
        tag="tezis"),
    "annotatsiya": dict(
        title="🌐 Annotatsiya (uz/ru/en)", ask="Annotatsiyasi kerak bo'lgan maqola matni yoki qisqacha mazmunini yuboring:",
        prompt=("Quyidagi matn asosida annotatsiya va kalit so'zlarni o'zbek, rus va ingliz tillarida tuzing "
                "(har biri taxminan 80-120 so'z, 5-7 kalit so'z):\n{input}"),
        tag="annotatsiya"),
    "adabiyot": dict(
        title="🔖 Adabiyotlar ro'yxati", ask="Rasmiylashtirilishi kerak bo'lgan manbalarni (har birini alohida qatorda) yuboring:",
        prompt=("Quyidagi manbalarni OAK talablariga mos adabiyotlar ro'yxati shaklida rasmiylashtiring "
                "(muallif, nom, nashr joyi, nashriyot, yil, sahifalar). Ma'lumot yetishmasa, uni to'qib qo'shmang — "
                "o'rniga [yetishmayapti: ...] deb belgilang:\n{input}"),
        tag="adabiyot"),
}

SECTIONS = {
    "talaba": dict(
        title="🎓 TALABA VA FILOLOGLAR", sub="Mumtoz meros · aruz · qadimgi til · etimologiya",
        tools=["gazal", "aruz", "qadim", "etim", "asar"]),
    "oqituvchi": dict(
        title="👨‍🏫 METODIST VA O'QITUVCHILAR", sub="Dars ishlanmasi · interfaol metod · attestatsiya",
        tools=["konspekt", "metod", "rubrika"], extra=[("📝 Attestatsiya testi (40 ta)", "attest_start")]),
    "izlanuvchi": dict(
        title="🔬 ILMIY IZLANUVCHILAR", sub="OAK maqola · tezis · annotatsiya · adabiyotlar",
        tools=["maqola", "tezis", "annotatsiya", "adabiyot"]),
    "asboblar": dict(
        title="🧰 TIL ASBOBLARI", sub="Tezkor yordamchilar — har kuni kerak bo'ladiganlar",
        tools=["imlo", "izoh", "etim"],
        extra=[("🔠 Alifbo konvertori", "conv_hub"), ("🧩 So'z yasovchi qo'shimchalar", "sfx_hub"),
               ("🧠 Aqliy mashq (ochiq topshiriq)", "open_next")]),
}

ESSAY_STRUCTURE = (
    "<b>📐 50 BALLIK ESSE SXEMASI</b>\n━━━━━━━━━━━━━━━\n\n"
    "<b>1. Kirish (3-4 gap)</b>\n"
    "• Mavzuning dolzarbligi: <i>«Bugungi kunda ... masalasi keng muhokama qilinmoqda.»</i>\n"
    "• Ikki qarashni qisqa tanishtirish: <i>«Bir tomon ... deb hisoblasa, ikkinchi tomon ... deb biladi.»</i>\n\n"
    "<b>2. Birinchi qarash (1 abzats)</b>\n"
    "• Fikr → sabab → misol: <i>«Birinchidan... Buning isboti sifatida...»</i>\n\n"
    "<b>3. Ikkinchi qarash (1 abzats)</b>\n"
    "• Qarama-qarshi dalil: <i>«Aksincha, ... tarafdorlari ... ta'kidlaydi.»</i>\n\n"
    "<b>4. Shaxsiy pozitsiya (1 abzats)</b>\n"
    "• <i>«Menimcha, ...»</i> — albatta dalil va hayotiy yoki adabiy misol bilan.\n\n"
    "<b>5. Xulosa (2-3 gap)</b>\n"
    "• <i>«Xulosa qilib aytganda, ...»</i> — yangi fikr qo'shmay, mohiyatni jamlash.\n\n"
    "<b>Muhim:</b>\n"
    "▫️ Ikkala qarashni ham yoritish shart.\n"
    "▫️ Bog'lovchi vositalar: <i>shu bois, biroq, aksincha, demak, bundan tashqari</i>.\n"
    "▫️ Gaplar qisqa va aniq; takrorlardan qoching.\n"
    "▫️ Yozib bo'lgach imlo va punktuatsiyani qayta o'qing."
)
