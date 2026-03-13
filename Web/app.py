from flask import Flask, render_template, render_template_string, request, jsonify, session, redirect, url_for, Response, send_from_directory
import sqlite3
import os
import re
import time
from datetime import timedelta
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "cok_gizli_star_tier_anahtari_2026" 
app.permanent_session_lifetime = timedelta(minutes=10)

ADMIN_SIFRE = """You Password"""

DB_PATH = "../tierlist.db" 
STEVE_UUID = "8667ba71b85a4004af54457a9734eed7"

# Klasörü uygulama başlatılırken güvenli yoldan (absolute path) oluşturuyoruz
REKLAM_KLASORU = os.path.join(app.root_path, "static", "reklamlar")
os.makedirs(REKLAM_KLASORU, exist_ok=True)

TIER_PUANLARI = {
    "HT1": 60, "LT1": 45, "HT2": 30, "LT2": 20, 
    "HT3": 10, "LT3": 6, "HT4": 4, "LT4": 3, 
    "HT5": 2, "LT5": 1
}

PUANDAN_TIERE = {v: k for k, v in TIER_PUANLARI.items()}

KIT_ISIMLERI = {
    "nethpot": "Nethpot", "sword": "Sword", "axe": "Axe", 
    "smp": "SMP", "diasmp": "DiaSMP", "mace": "Mace", 
    "pot": "Pot", "uhc": "UHC", "crystal": "Crystal", "vanilla": "Crystal"
}

def puandan_tiere_cevir(puan):
    if not PUANDAN_TIERE: return "-"
    closest = min(PUANDAN_TIERE.keys(), key=lambda k: abs(k - puan))
    return PUANDAN_TIERE[closest]

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def db_onar():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oyuncular (
            id INTEGER PRIMARY KEY AUTOINCREMENT, minecraft_nick TEXT, uuid TEXT,
            discord_id INTEGER, kit TEXT, tier TEXT, region TEXT, tester_id INTEGER,
            skor TEXT, klan TEXT, tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klan_bilgi (
            klan_adi TEXT PRIMARY KEY, kurucu_nick TEXT, kurucu_discord TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hile_listesi (
            kayit_id TEXT PRIMARY KEY, discord_id INTEGER, minecraft_nick TEXT,
            sebep TEXT, sure_ay INTEGER, bitis_tarihi TIMESTAMP, yonetici_id INTEGER,
            kanit_url TEXT, uuid TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reklam_discordlar (
            id INTEGER PRIMARY KEY AUTOINCREMENT, isim TEXT, aciklama TEXT,
            url TEXT, gorsel_url TEXT
        )
    """)
    try: cursor.execute("ALTER TABLE oyuncular ADD COLUMN skor TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE oyuncular ADD COLUMN klan TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE klan_bilgi ADD COLUMN discord_url TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE klan_bilgi ADD COLUMN renk TEXT DEFAULT '#a855f7'")
    except sqlite3.OperationalError: pass
    conn.commit()
    conn.close()

db_onar()

def get_common_data():
    conn = get_db_connection()
    oyuncular_db = conn.execute('SELECT * FROM oyuncular').fetchall()
    klanlar_db = conn.execute('SELECT * FROM klan_bilgi').fetchall()
    reklamlar_db = conn.execute('SELECT * FROM reklam_discordlar').fetchall()
    conn.close()

    klanlar_dict = {}
    for row in klanlar_db:
        k_adi = row['klan_adi']
        renk = dict(row).get('renk') if dict(row).get('renk') else '#a855f7'
        klanlar_dict[k_adi] = {"isim": k_adi, "kurucu": row['kurucu_nick'], "renk": renk, "total_points": 0, "oyuncu_sayisi": 0, "all_tiers": [], "kit_puanlari": {}}

    oyuncular_dict = {}
    for row in oyuncular_db:
        nick = row['minecraft_nick']
        aktif_uuid = row['uuid'] if dict(row).get('uuid') and row['uuid'] != 'non-premium' else STEVE_UUID
        klan = row['klan'] if dict(row).get('klan') else None

        if not klan:
            for k_adi, k_data in klanlar_dict.items():
                if k_data['kurucu'].lower() == nick.lower():
                    klan = k_adi
                    break

        if nick not in oyuncular_dict:
            klan_renk = "#a855f7"
            is_founder = False
            
            if klan and klan in klanlar_dict:
                klan_renk = klanlar_dict[klan]["renk"]
                if klanlar_dict[klan]["kurucu"].lower() == nick.lower():
                    is_founder = True

            oyuncular_dict[nick] = {
                "nick": nick, "uuid": aktif_uuid, "total_points": 0, "kits": {}, 
                "klan": klan, "klan_renk": klan_renk, "is_founder": is_founder
            }
        
        tier = row['tier']
        kit = KIT_ISIMLERI.get(row['kit'].lower(), row['kit'].capitalize()) 
        oyuncular_dict[nick]["kits"][kit] = tier
        oyuncular_dict[nick]["total_points"] += TIER_PUANLARI.get(tier, 0)

    sirali_oyuncular = sorted(oyuncular_dict.values(), key=lambda x: x['total_points'], reverse=True)
    
    for p in sirali_oyuncular:
        k = p.get("klan")
        if k:
            if k not in klanlar_dict: klanlar_dict[k] = {"isim": k, "kurucu": "", "renk": "#a855f7", "total_points": 0, "oyuncu_sayisi": 0, "all_tiers": [], "kit_puanlari": {}}
            klanlar_dict[k]["total_points"] += p["total_points"]
            klanlar_dict[k]["oyuncu_sayisi"] += 1
            for kit_name, tier in p["kits"].items():
                puan = TIER_PUANLARI.get(tier, 0)
                klanlar_dict[k]["all_tiers"].append(puan)
                if kit_name not in klanlar_dict[k]["kit_puanlari"]:
                    klanlar_dict[k]["kit_puanlari"][kit_name] = []
                klanlar_dict[k]["kit_puanlari"][kit_name].append(puan)
                
    klanlar_list = []
    for v in klanlar_dict.values():
        if v["all_tiers"]:
            v["en_iyi_tier"] = puandan_tiere_cevir(max(v["all_tiers"]))
            v["ortalama_tier"] = puandan_tiere_cevir(sum(v["all_tiers"]) / len(v["all_tiers"]))
        else:
            v["en_iyi_tier"] = "-"
            v["ortalama_tier"] = "-"
            
        best_kit = "-"
        best_kit_avg_tier = "-"
        if v["kit_puanlari"]:
            highest_avg = -1
            for k_name, points_list in v["kit_puanlari"].items():
                avg = sum(points_list) / len(points_list)
                if avg > highest_avg:
                    highest_avg = avg
                    best_kit = k_name
            best_kit_avg_tier = puandan_tiere_cevir(highest_avg)
            
        v["en_iyi_kit"] = best_kit
        v["en_iyi_kit_tier"] = best_kit_avg_tier
        klanlar_list.append(v)
        
    sirali_klanlar = sorted(klanlar_list, key=lambda x: x['total_points'], reverse=True)
    reklamlar = [dict(r) for r in reklamlar_db]
    
    return sirali_oyuncular, sirali_klanlar, reklamlar

@app.route('/sitemap.xml')
def sitemap():
    return send_from_directory('static', 'sitemap.xml')

@app.route('/robots.txt')
def robots():
    robots_content = "User-agent: *\nDisallow: /admin/\nAllow: /\n"
    return Response(robots_content, mimetype="text/plain")

@app.route('/')
def index():
    oyuncular, klanlar, reklamlar = get_common_data()
    return render_template('index.html', oyuncular=oyuncular, klanlar=klanlar, reklamlar=reklamlar)

@app.route('/en')
def index_en():
    oyuncular, klanlar, reklamlar = get_common_data()
    return render_template('index_en.html', oyuncular=oyuncular, klanlar=klanlar, reklamlar=reklamlar)

@app.route('/api/oyuncu/<nick>')
def oyuncu_getir(nick):
    conn = get_db_connection()
    hile_kaydi = conn.execute('SELECT * FROM hile_listesi WHERE minecraft_nick COLLATE NOCASE = ?', (nick,)).fetchone()
    
    if hile_kaydi:
        conn.close()
        is_premium = dict(hile_kaydi).get('uuid') and hile_kaydi['uuid'] != 'non-premium'
        return jsonify({
            "nick": hile_kaydi['minecraft_nick'], "uuid": hile_kaydi['uuid'] if is_premium else STEVE_UUID,
            "total_points": 0, "kits": {}, "is_banned": True, "ban_reason": hile_kaydi['sebep'], "is_premium": bool(is_premium)
        })

    veriler = conn.execute('SELECT * FROM oyuncular WHERE minecraft_nick COLLATE NOCASE = ?', (nick,)).fetchall()
    
    if not veriler: 
        conn.close()
        return jsonify({"error": "Oyuncu bulunamadı!"}), 404

    is_premium = dict(veriler[0]).get('uuid') and veriler[0]['uuid'] != 'non-premium'
    
    klan_adi = dict(veriler[0]).get('klan')
    if not klan_adi:
        kurucu_kayit = conn.execute('SELECT klan_adi FROM klan_bilgi WHERE kurucu_nick COLLATE NOCASE = ?', (nick,)).fetchone()
        if kurucu_kayit:
            klan_adi = kurucu_kayit['klan_adi']
            
    conn.close()

    oyuncu_data = {
        "nick": veriler[0]['minecraft_nick'], "uuid": veriler[0]['uuid'] if is_premium else STEVE_UUID,
        "region": veriler[0]['region'], "klan": klan_adi, "total_points": 0, "kits": {}, "is_banned": False, "is_premium": bool(is_premium)
    }

    for row in veriler:
        kit = KIT_ISIMLERI.get(row['kit'].lower(), row['kit'].capitalize())
        oyuncu_data["kits"][kit] = row['tier']
        oyuncu_data["total_points"] += TIER_PUANLARI.get(row['tier'], 0)

    return jsonify(oyuncu_data)

@app.route('/api/klan/<klan_adi>')
def klan_getir(klan_adi):
    conn = get_db_connection()
    klan_bilgi = conn.execute('SELECT * FROM klan_bilgi WHERE klan_adi COLLATE NOCASE = ?', (klan_adi,)).fetchone()
    if not klan_bilgi:
        conn.close()
        return jsonify({"error": "Klan bulunamadı"}), 404

    kurucu_nick = klan_bilgi['kurucu_nick']
    discord_url = dict(klan_bilgi).get('discord_url', '')
    renk = dict(klan_bilgi).get('renk', '#a855f7')
    
    oyuncular_db = conn.execute('SELECT minecraft_nick, uuid, kit, tier FROM oyuncular WHERE klan COLLATE NOCASE = ? OR minecraft_nick COLLATE NOCASE = ?', (klan_adi, kurucu_nick)).fetchall()
    conn.close()

    uyeler, toplam_puan, all_tiers, kit_puanlari = {}, 0, [], {}

    for row in oyuncular_db:
        nick = row['minecraft_nick']
        if nick not in uyeler:
            is_premium = bool(dict(row).get('uuid') and row['uuid'] != 'non-premium')
            uyeler[nick] = {"nick": nick, "uuid": row['uuid'] if is_premium else STEVE_UUID, "kits": {}, "toplam_puan": 0}

        kit = KIT_ISIMLERI.get(row['kit'].lower(), row['kit'].capitalize())
        puan = TIER_PUANLARI.get(row['tier'], 0)

        uyeler[nick]["kits"][kit] = row['tier']
        uyeler[nick]["toplam_puan"] += puan
        toplam_puan += puan
        all_tiers.append(puan)
        
        if kit not in kit_puanlari:
            kit_puanlari[kit] = []
        kit_puanlari[kit].append(puan)

    siralik_uyeler = sorted(uyeler.values(), key=lambda x: x['toplam_puan'], reverse=True)
    
    best_kit = "-"
    best_kit_avg_tier = "-"
    if kit_puanlari:
        highest_avg = -1
        for k_name, points_list in kit_puanlari.items():
            avg = sum(points_list) / len(points_list)
            if avg > highest_avg:
                highest_avg = avg
                best_kit = k_name
        best_kit_avg_tier = puandan_tiere_cevir(highest_avg)
    
    return jsonify({
        "isim": klan_bilgi['klan_adi'], "kurucu_nick": kurucu_nick, "discord_url": discord_url, "renk": renk,
        "toplam_puan": toplam_puan, "uye_sayisi": len(siralik_uyeler),
        "en_iyi_tier": puandan_tiere_cevir(max(all_tiers)) if all_tiers else "-",
        "en_iyi_kit": best_kit,
        "en_iyi_kit_tier": best_kit_avg_tier,
        "ortalama_tier": puandan_tiere_cevir(sum(all_tiers) / len(all_tiers)) if all_tiers else "-",
        "uyeler": siralik_uyeler
    })

@app.route('/api/mod_data')
def api_mod_data():
    conn = get_db_connection()
    oyuncular_db = conn.execute('SELECT minecraft_nick, kit, tier FROM oyuncular').fetchall()
    hileler_db = conn.execute('SELECT minecraft_nick FROM hile_listesi').fetchall()
    conn.close()

    banned_players = [row['minecraft_nick'].lower() for row in hileler_db]
    mod_data = {}

    for row in oyuncular_db:
        nick = row['minecraft_nick']
        nick_lower = nick.lower()
        
        if nick_lower in banned_players:
            mod_data[nick_lower] = {
                "display_name": nick,
                "is_banned": True,
                "best_tier": "BANNED",
                "best_puan": -1,
                "color": "#ff0000",
                "all_kits": {}
            }
            continue

        kit = row['kit']
        kit_standard = KIT_ISIMLERI.get(kit.lower(), kit.capitalize())
        tier = row['tier']
        puan = TIER_PUANLARI.get(tier, 0)

        if nick_lower not in mod_data:
            mod_data[nick_lower] = {
                "display_name": nick,
                "is_banned": False,
                "best_tier": tier,
                "best_puan": puan,
                "all_kits": {}
            }
        
        mod_data[nick_lower]["all_kits"][kit_standard] = tier
        
        if puan > mod_data[nick_lower]["best_puan"]:
            mod_data[nick_lower]["best_tier"] = tier
            mod_data[nick_lower]["best_puan"] = puan

    return jsonify(mod_data)

def isim_temizle(isim, filename):
    ext = os.path.splitext(secure_filename(filename))[1].lower()
    if not ext:
        ext = ".png"
    safe_isim = re.sub(r'[^a-zA-Z0-9]', '_', isim)
    safe_isim = re.sub(r'_+', '_', safe_isim).strip('_')
    if not safe_isim:
        safe_isim = "sponsor"
    # Tarayıcının önbellekte takılı kalmaması için ismin sonuna zaman damgası ekliyoruz
    return f"{safe_isim}_{int(time.time())}{ext}"

ADMIN_HTML = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Star Tier List | Admin Panel</title><script src="https://cdn.tailwindcss.com"></script>
    <style>
        body { background-color: #0a0a0c; color: white; font-family: 'Inter', sans-serif; }
        .hide-scrollbar::-webkit-scrollbar { display: none; }
        .hide-scrollbar { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="flex flex-col items-center justify-center min-h-screen p-4">
    {% if not session.get('admin_logged_in') %}
        <script>sessionStorage.removeItem('star_admin_session');</script>
        <div class="bg-[#121216] border border-gray-800 p-8 rounded-2xl shadow-2xl max-w-sm w-full text-center">
            <h1 class="text-3xl font-black mb-6 text-orange-500">YÖNETİCİ</h1>
            <form method="POST" action="/admin/login" class="flex flex-col gap-4" onsubmit="sessionStorage.setItem('star_admin_session', 'true');">
                <input type="password" name="sifre" placeholder="Şifreyi girin..." class="px-4 py-3 rounded-xl bg-[#1a1a20] border border-gray-700 focus:border-orange-500 outline-none text-white">
                <button type="submit" class="bg-orange-600 hover:bg-orange-700 text-white font-bold py-3 rounded-xl transition">Giriş Yap</button>
            </form>
        </div>
    {% else %}
        <div class="bg-[#121216] border border-gray-800 p-8 rounded-2xl shadow-2xl w-full max-w-4xl relative">
            <div class="flex justify-between items-center mb-8 border-b border-gray-800 pb-4">
                <h1 class="text-3xl font-black text-orange-500">KONTROL PANELİ</h1>
                <a href="/admin/logout" onclick="sessionStorage.removeItem('star_admin_session');" class="bg-red-600 hover:bg-red-700 px-4 py-2 rounded-lg font-bold">Çıkış Yap</a>
            </div>
            
            <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
                <div class="bg-[#1a1a20] p-6 rounded-xl border border-gray-700/50 flex flex-col">
                    <h2 class="text-xl font-bold mb-4 text-purple-400">👑 Klan Ayarları (Renk & Discord)</h2>
                    <form method="POST" action="/admin/klan_ayarla" class="flex flex-col gap-3 mb-6">
                        <select name="klan_adi" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                            <option value="">Klan Seçin...</option>
                            {% for k in klanlar %}<option value="{{ k.klan_adi }}">{{ k.klan_adi }}</option>{% endfor %}
                        </select>
                        <select name="renk" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white">
                            <option value="#a855f7">Mor (Varsayılan)</option>
                            <option value="#ef4444" style="color:#ef4444">Kırmızı</option>
                            <option value="#3b82f6" style="color:#3b82f6">Mavi</option>
                            <option value="#22c55e" style="color:#22c55e">Yeşil</option>
                            <option value="#eab308" style="color:#eab308">Sarı</option>
                            <option value="#f97316" style="color:#f97316">Turuncu</option>
                            <option value="#ec4899" style="color:#ec4899">Pembe</option>
                            <option value="#06b6d4" style="color:#06b6d4">Turkuaz</option>
                            <option value="#10b981" style="color:#10b981">Zümrüt Yeşili</option>
                            <option value="#6366f1" style="color:#6366f1">İndigo</option>
                            <option value="#f43f5e" style="color:#f43f5e">Gül Rengi</option>
                            <option value="#84cc16" style="color:#84cc16">Limon Yeşili</option>
                            <option value="#f59e0b" style="color:#f59e0b">Kehribar</option>
                            <option value="#0ea5e9" style="color:#0ea5e9">Gök Mavisi</option>
                            <option value="#d946ef" style="color:#d946ef">Fuşya</option>
                            <option value="#8b5cf6" style="color:#8b5cf6">Menekşe</option>
                            <option value="#dc143c" style="color:#dc143c">Koyu Kırmızı (Crimson)</option>
                            <option value="#ffd700" style="color:#ffd700">Altın</option>
                            <option value="#c0c0c0" style="color:#c0c0c0">Gümüş</option>
                            <option value="#000000" style="background:#fff; color:#000">Siyah</option>
                            <option value="#ffffff" style="color:#fff">Beyaz</option>
                            <option value="#000080" style="color:#000080">Lacivert</option>
                            <option value="#800000" style="color:#800000">Bordo</option>
                            <option value="#808000" style="color:#808000">Zeytin Yeşili</option>
                            <option value="#008080" style="color:#008080">Deniz Mavisi</option>
                        </select>
                        <input type="url" name="discord_url" placeholder="Varsa Discord Davet Linki" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white">
                        <button type="submit" class="bg-purple-600 hover:bg-purple-700 py-2 rounded-lg font-bold mt-2 transition">Ayarları Kaydet</button>
                    </form>

                    <h3 class="text-sm font-bold text-gray-400 mb-3 border-b border-gray-700 pb-1">Mevcut Klan Ayarları</h3>
                    <div class="flex flex-col gap-2 overflow-y-auto max-h-40 hide-scrollbar pr-1">
                        {% for k in klanlar %}
                            <div class="flex justify-between items-center bg-[#121216] p-3 rounded-lg border border-gray-700/50 group">
                                <div class="flex flex-col truncate pr-2">
                                    <div class="flex items-center gap-2">
                                        <div class="w-3 h-3 rounded-full" style="background-color: {{ k.renk|default('#a855f7', true) }};"></div>
                                        <span class="font-bold text-gray-300 text-sm">{{ k.klan_adi }}</span>
                                    </div>
                                    <span class="text-xs text-gray-500 truncate">{{ k.discord_url if k.discord_url else 'Discord Eklenmemiş' }}</span>
                                </div>
                                {% if k.discord_url %}
                                <a href="/admin/klan_discord_sil/{{ k.klan_adi }}" class="bg-red-900/40 hover:bg-red-800 text-red-300 px-3 py-1.5 rounded-md text-xs font-bold border border-red-800/50 transition shrink-0">DC Sil</a>
                                {% endif %}
                            </div>
                        {% endfor %}
                    </div>
                </div>

                <div class="bg-[#1a1a20] p-6 rounded-xl border border-gray-700/50">
                    <h2 class="text-xl font-bold mb-4 text-blue-400">📢 Sponsor Ekle</h2>
                    <form method="POST" action="/admin/reklam_ekle" enctype="multipart/form-data" class="flex flex-col gap-3">
                        <input type="text" name="isim" placeholder="Sunucu Adı (Örn: RVAT)" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                        <input type="text" name="aciklama" placeholder="Kısa Açıklama" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                        <input type="url" name="url" placeholder="Discord Davet Linki" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                        <div class="border border-dashed border-gray-600 hover:border-blue-500 transition rounded-lg p-3 text-center bg-[#121216] mt-1">
                            <label class="text-xs text-gray-400 block mb-2 font-bold uppercase tracking-wider">Logo Yükle (Resim Dosyası)</label>
                            <input type="file" name="gorsel" accept="image/*" class="text-sm w-full text-gray-400 file:mr-4 file:py-1.5 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-blue-600/20 file:text-blue-400 hover:file:bg-blue-600 hover:file:text-white transition cursor-pointer" required>
                        </div>
                        <button type="submit" class="bg-blue-600 hover:bg-blue-700 py-2 rounded-lg font-bold mt-2 transition">Sunucuyu Ekle</button>
                    </form>
                </div>
            </div>

            <div class="mt-8">
                <h2 class="text-xl font-bold mb-4 text-gray-400">Aktif Sponsor Sunucular</h2>
                <div class="flex flex-col gap-3">
                    {% for r in reklamlar %}
                    <div class="flex justify-between items-center bg-[#1a1a20] p-4 rounded-xl border border-gray-700/50">
                        <div class="flex items-center gap-4">
                            <img src="{{ r.gorsel_url }}" class="w-12 h-12 rounded-xl object-cover border border-gray-600">
                            <div><div class="font-black text-white">{{ r.isim }}</div><div class="text-xs text-gray-400">{{ r.aciklama }}</div></div>
                        </div>
                        <div class="flex gap-2">
                            <button onclick="openEditModal('{{ r.id }}', '{{ r.isim }}', '{{ r.aciklama }}', '{{ r.url }}')" class="bg-blue-900/40 hover:bg-blue-800 text-blue-300 px-4 py-2 rounded-lg text-sm font-bold border border-blue-700/50 transition">Değiştir</button>
                            <a href="/admin/reklam_sil/{{ r.id }}" class="bg-red-900/50 hover:bg-red-800 text-red-300 px-4 py-2 rounded-lg text-sm font-bold border border-red-700 transition">Kaldır</a>
                        </div>
                    </div>
                    {% else %}<div class="text-gray-600 text-sm text-center py-4 bg-[#1a1a20] rounded-xl border border-gray-800">Hiç sponsor sunucu eklenmemiş.</div>{% endfor %}
                </div>
            </div>
            <div class="mt-6 text-center"><a href="/" class="text-gray-500 hover:text-white underline text-sm transition">Tierlist'e Dön</a></div>
        </div>

        <div id="editModal" class="fixed inset-0 bg-black/90 hidden items-center justify-center z-50 p-4 backdrop-blur-sm">
            <div class="bg-[#1a1a20] border border-blue-900/50 w-full max-w-md rounded-2xl p-6 relative shadow-2xl">
                <button onclick="document.getElementById('editModal').classList.add('hidden'); document.getElementById('editModal').classList.remove('flex');" class="absolute top-4 right-4 text-gray-400 hover:text-white bg-gray-900 rounded-full w-8 h-8 flex items-center justify-center">✕</button>
                <h2 class="text-xl font-black mb-4 text-blue-400">SPONSOR DEĞİŞTİR</h2>
                <form method="POST" action="/admin/reklam_duzenle" enctype="multipart/form-data" class="flex flex-col gap-3">
                    <input type="hidden" name="r_id" id="edit_r_id">
                    <input type="text" name="isim" id="edit_isim" placeholder="Sunucu Adı" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                    <input type="text" name="aciklama" id="edit_aciklama" placeholder="Kısa Açıklama" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                    <input type="url" name="url" id="edit_url" placeholder="Discord Linki" class="px-4 py-2 rounded-lg bg-[#121216] border border-gray-700 text-white" required>
                    <div class="border border-dashed border-gray-600 hover:border-blue-500 transition rounded-lg p-3 text-center bg-[#121216] mt-1">
                        <label class="text-xs text-gray-400 block mb-2 font-bold uppercase">Yeni Logo (Boş bırakırsan eski logo kalır)</label>
                        <input type="file" name="gorsel" accept="image/*" class="text-sm w-full text-gray-400 file:mr-4 file:py-1.5 file:px-4 file:rounded-lg file:border-0 file:text-xs file:font-bold file:bg-blue-600/20 file:text-blue-400 hover:file:bg-blue-600 hover:file:text-white transition cursor-pointer">
                    </div>
                    <button type="submit" class="bg-blue-600 hover:bg-blue-700 py-2 rounded-lg font-bold mt-2 transition text-white">Değişiklikleri Kaydet</button>
                </form>
            </div>
        </div>

        <script>
            if (!sessionStorage.getItem('star_admin_session')) {
                window.location.replace('/admin/logout');
            }
            let inactivityTime = function () {
                let time;
                function logout() { sessionStorage.removeItem('star_admin_session'); window.location.replace('/admin/logout'); }
                function resetTimer() { clearTimeout(time); time = setTimeout(logout, 600000); }
                window.onload = resetTimer; document.onmousemove = resetTimer; document.onkeydown = resetTimer; document.onscroll = resetTimer; document.onclick = resetTimer;
            };
            inactivityTime();
            function openEditModal(id, isim, aciklama, url) {
                document.getElementById('edit_r_id').value = id; document.getElementById('edit_isim').value = isim; document.getElementById('edit_aciklama').value = aciklama; document.getElementById('edit_url').value = url;
                let modal = document.getElementById('editModal'); modal.classList.remove('hidden'); modal.classList.add('flex');
            }
        </script>
    {% endif %}
</body>
</html>
"""

@app.route('/admin')
def admin_page():
    conn = get_db_connection()
    klanlar = conn.execute('SELECT * FROM klan_bilgi').fetchall()
    reklamlar = conn.execute('SELECT * FROM reklam_discordlar').fetchall()
    conn.close()
    return render_template_string(ADMIN_HTML, klanlar=klanlar, reklamlar=reklamlar)

@app.route('/admin/login', methods=['POST'])
def admin_login():
    girilen_sifre = request.form.get('sifre', '')
    temiz_girilen = re.sub(r'\s+', '', girilen_sifre)
    temiz_beklenen = re.sub(r'\s+', '', ADMIN_SIFRE)
    if temiz_girilen == temiz_beklenen: 
        session.permanent = True
        session['admin_logged_in'] = True
    return redirect('/admin')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin')

@app.route('/admin/klan_ayarla', methods=['POST'])
def admin_klan_ayarla():
    if not session.get('admin_logged_in'): return redirect('/admin')
    klan_adi = request.form.get('klan_adi')
    renk = request.form.get('renk')
    url = request.form.get('discord_url')
    if klan_adi:
        conn = get_db_connection()
        if url and url.strip() != "": conn.execute('UPDATE klan_bilgi SET renk = ?, discord_url = ? WHERE klan_adi = ?', (renk, url, klan_adi))
        else: conn.execute('UPDATE klan_bilgi SET renk = ? WHERE klan_adi = ?', (renk, klan_adi))
        conn.commit()
        conn.close()
    return redirect('/admin')

@app.route('/admin/klan_discord_sil/<klan_adi>')
def admin_klan_discord_sil(klan_adi):
    if not session.get('admin_logged_in'): return redirect('/admin')
    conn = get_db_connection()
    conn.execute('UPDATE klan_bilgi SET discord_url = NULL WHERE klan_adi = ?', (klan_adi,))
    conn.commit()
    conn.close()
    return redirect('/admin')

@app.route('/admin/reklam_ekle', methods=['POST'])
def admin_reklam_ekle():
    if not session.get('admin_logged_in'): return redirect('/admin')
    isim = request.form.get('isim'); aciklama = request.form.get('aciklama'); url = request.form.get('url'); dosya = request.files.get('gorsel')
    gorsel_url = ""
    if dosya and dosya.filename:
        dosya_adi = isim_temizle(isim, dosya.filename)
        # RESMİN KESİN OLARAK WEB KLASÖRÜNE İNMESİ İÇİN app.root_path KULLANIYORUZ
        kayit_yolu = os.path.join(app.root_path, "static", "reklamlar", dosya_adi)
        dosya.save(kayit_yolu)
        gorsel_url = f"/static/reklamlar/{dosya_adi}" 
        
    conn = get_db_connection()
    conn.execute('INSERT INTO reklam_discordlar (isim, aciklama, url, gorsel_url) VALUES (?, ?, ?, ?)', (isim, aciklama, url, gorsel_url))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/admin/reklam_duzenle', methods=['POST'])
def admin_reklam_duzenle():
    if not session.get('admin_logged_in'): return redirect('/admin')
    r_id = request.form.get('r_id'); isim = request.form.get('isim'); aciklama = request.form.get('aciklama'); url = request.form.get('url'); dosya = request.files.get('gorsel')
    conn = get_db_connection()
    
    if dosya and dosya.filename:
        eski = conn.execute('SELECT gorsel_url FROM reklam_discordlar WHERE id = ?', (r_id,)).fetchone()
        if eski and eski['gorsel_url']:
            try: 
                # Eski resmi silerken de mutlak yol (absolute path) kullanıyoruz
                eski_yol = os.path.join(app.root_path, eski['gorsel_url'].lstrip('/'))
                os.remove(eski_yol)
            except: pass
            
        dosya_adi = isim_temizle(isim, dosya.filename)
        kayit_yolu = os.path.join(app.root_path, "static", "reklamlar", dosya_adi)
        dosya.save(kayit_yolu)
        gorsel_url = f"/static/reklamlar/{dosya_adi}"
        conn.execute('UPDATE reklam_discordlar SET isim=?, aciklama=?, url=?, gorsel_url=? WHERE id=?', (isim, aciklama, url, gorsel_url, r_id))
    else:
        conn.execute('UPDATE reklam_discordlar SET isim=?, aciklama=?, url=? WHERE id=?', (isim, aciklama, url, r_id))
    conn.commit(); conn.close()
    return redirect('/admin')

@app.route('/admin/reklam_sil/<int:r_id>')
def admin_reklam_sil(r_id):
    if not session.get('admin_logged_in'): return redirect('/admin')
    conn = get_db_connection()
    reklam = conn.execute('SELECT gorsel_url FROM reklam_discordlar WHERE id = ?', (r_id,)).fetchone()
    if reklam and reklam['gorsel_url']:
        dosya_yolu = os.path.join(app.root_path, reklam['gorsel_url'].lstrip('/'))
        if os.path.exists(dosya_yolu):
            try: os.remove(dosya_yolu)
            except: pass
    conn.execute('DELETE FROM reklam_discordlar WHERE id = ?', (r_id,))
    conn.commit(); conn.close()
    return redirect('/admin')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
