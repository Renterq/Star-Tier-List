import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import json
import os
import sqlite3
import aiohttp
import random
import traceback
from typing import List

# ================= AYARLAR VE SABİTLER =================
SAHIP_IDLER = [533901413881741313, 764029369085591582, 1224166722840563802]
AAC_ROLE_ID = 1475326618384859248 
ROLLER_DOSYASI = "kit_rolleri.json"
AYARLAR_DOSYASI = "ayarlar.json" 

# ELYTRA VE VANILLA YOK! SADECE 9 ADET KİT VAR (CRYSTAL EKLENDİ)
KITLER = ["Nethpot", "Sword", "Axe", "SMP", "DiaSMP", "Mace", "Pot", "UHC", "Crystal"]
TIERLAR = ["HT1", "LT1", "HT2", "LT2", "HT3", "LT3", "HT4", "LT4", "HT5", "LT5"]
STEVE_UUID = "8667ba71b85a4004af54457a9734eed7" 

intents = discord.Intents.default()
intents.message_content = True
intents.members = True 

os.makedirs("web/static/klanlar", exist_ok=True)

# ================= VERİTABANI YÖNETİMİ =================
def rolleri_yukle():
    if os.path.exists(ROLLER_DOSYASI):
        with open(ROLLER_DOSYASI, "r") as f:
            data = json.load(f)
            for kit in KITLER:
                if kit.lower() not in data: 
                    data[kit.lower()] = []
            return data
    return {kit.lower(): [] for kit in KITLER}

def rolleri_kaydet(roller):
    with open(ROLLER_DOSYASI, "w") as f:
        json.dump(roller, f)

def ayarlari_yukle():
    if os.path.exists(AYARLAR_DOSYASI):
        with open(AYARLAR_DOSYASI, "r") as f:
            return json.load(f)
    return {"kit_bekleme_rolleri": {}, "emojiler": {}, "hile_rolu": None}

def ayarlari_kaydet(ayarlar):
    with open(AYARLAR_DOSYASI, "w") as f:
        json.dump(ayarlar, f)

def vt_kur():
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS oyuncular (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            minecraft_nick TEXT,
            uuid TEXT,
            discord_id INTEGER,
            kit TEXT,
            tier TEXT,
            region TEXT, 
            tester_id INTEGER,
            skor TEXT,
            klan TEXT,
            tarih TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ayarlar (
            ayar_adi TEXT PRIMARY KEY,
            deger TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hile_listesi (
            kayit_id TEXT PRIMARY KEY,
            discord_id INTEGER,
            minecraft_nick TEXT,
            sebep TEXT,
            sure_ay INTEGER,
            bitis_tarihi TIMESTAMP,
            yonetici_id INTEGER,
            kanit_url TEXT,
            uuid TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS klan_bilgi (
            klan_adi TEXT PRIMARY KEY,
            kurucu_nick TEXT,
            kurucu_discord TEXT
        )
    """)
    try: cursor.execute("ALTER TABLE oyuncular ADD COLUMN skor TEXT")
    except sqlite3.OperationalError: pass
    try: cursor.execute("ALTER TABLE oyuncular ADD COLUMN klan TEXT")
    except sqlite3.OperationalError: pass
    conn.commit()
    conn.close()

KIT_ROLLER = rolleri_yukle() 
AYARLAR = ayarlari_yukle()

QUEUES = {kit.lower(): [] for kit in KITLER} 
QUEUE_MESSAGES = {kit.lower(): None for kit in KITLER}
ACTIVE_TESTERS = {kit.lower(): [] for kit in KITLER}
AKTIF_TEST_SAYISI = {kit.lower(): 0 for kit in KITLER}
WAITLIST_USERS = {} 

# ================= YARDIMCI FONKSİYONLAR =================
def is_tester(user):
    if user.id in SAHIP_IDLER or user.guild_permissions.administrator: return True
    if isinstance(user, discord.Member):
        for roller in KIT_ROLLER.values():
            if any(role.id in roller for role in user.roles): return True
    return False

def can_manage_kit(user, kit_adi):
    if user.id in SAHIP_IDLER or user.guild_permissions.administrator: return True
    if isinstance(user, discord.Member):
        if any(role.id in KIT_ROLLER.get(kit_adi.lower(), []) for role in user.roles): return True
    return False

def hile_kontrol(interaction: discord.Interaction):
    hile_rol_id = AYARLAR.get("hile_rolu")
    if hile_rol_id and interaction.guild.get_role(hile_rol_id) in interaction.user.roles: return True
    return False

async def minecraft_uuid_al(nick):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"https://api.mojang.com/users/profiles/minecraft/{nick}") as response:
            if response.status == 200:
                data = await response.json()
                return data["id"] 
            return None 

def uzun_tier_ismi(kisa_tier):
    if kisa_tier.startswith("HT"): return f"High Tier {kisa_tier[-1]}"
    elif kisa_tier.startswith("LT"): return f"Low Tier {kisa_tier[-1]}"
    return kisa_tier

def get_kit_emoji(kit_adi):
    k_lower = kit_adi.lower()
    emojiler = AYARLAR.get("emojiler", {})
    if k_lower in emojiler:
        return emojiler[k_lower]
    
    varsayilanlar = {
        "nethpot": "🧪", 
        "sword": "⚔️", 
        "axe": "🪓", 
        "smp": "🌳", 
        "diasmp": "💎", 
        "mace": "🔨", 
        "pot": "🏺", 
        "uhc": "🍎", 
        "crystal": "🔮"
    }
    return varsayilanlar.get(k_lower, "🎮")

async def tier_rolu_guncelle(guild, member, kit, yeni_tier, eski_tier=None):
    if not isinstance(member, discord.Member):
        return

    # Eski rolü varsa üzerinden al
    if eski_tier:
        eski_rol_adi = f"{kit} {eski_tier}".lower()
        for role in member.roles:
            if role.name.lower() == eski_rol_adi:
                try: 
                    await member.remove_roles(role)
                except Exception as e: 
                    print(f"Eski rol alınırken hata: {e}")
                pass

    # Yeni rolü bul ve ver
    yeni_rol_adi = f"{kit} {yeni_tier}".lower()
    for role in guild.roles:
        if role.name.lower() == yeni_rol_adi:
            try: 
                await member.add_roles(role)
            except Exception as e: 
                print(f"Yeni rol verilirken hata: {e}")
            break


# ================= BOT SINIFI =================
class UltimateBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        vt_kur()
        self.add_view(MainWaitlistView())
        self.add_view(MainControlPanelView())
        for kit in KITLER:
            self.add_view(QueueView(kit.lower()))
            self.add_view(CloseTicketView(kit.lower()))
            self.add_view(TesterActionView(kit.lower()))
        self.tree.on_error = self.on_app_command_error
        await self.tree.sync()
        self.hile_suresi_kontrol.start() 

    async def on_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ **Bu komutu kullanma yetkiniz yok! / You do not have permission to use this command!**", 
                    ephemeral=True
                )
        else:
            print(f"Bilinmeyen Hata: {error}")

    @tasks.loop(minutes=15)
    async def hile_suresi_kontrol(self):
        conn = sqlite3.connect("tierlist.db")
        cursor = conn.cursor()
        cursor.execute("SELECT kayit_id, discord_id, minecraft_nick, sure_ay, bitis_tarihi, uuid FROM hile_listesi WHERE bitis_tarihi <= CURRENT_TIMESTAMP")
        dolanlar = cursor.fetchall()

        if dolanlar:
            cursor.execute("SELECT deger FROM ayarlar WHERE ayar_adi = 'hile_kanali'")
            kanal_ayari = cursor.fetchone()
            kanal = self.get_channel(int(kanal_ayari[0])) if kanal_ayari else None
            
            for row in dolanlar:
                islem_id, d_id, nick, sure, bitis, uuid = row
                
                if kanal and kanal.guild:
                    hedef_kullanici = kanal.guild.get_member(d_id)
                    hile_rol_id = AYARLAR.get("hile_rolu")
                    if hedef_kullanici and hile_rol_id:
                        hile_rol = kanal.guild.get_role(hile_rol_id)
                        if hile_rol:
                            try: 
                                await hedef_kullanici.remove_roles(hile_rol)
                            except: 
                                pass

                if kanal:
                    gorsel_uuid = STEVE_UUID if uuid == "non-premium" else uuid
                    embed = discord.Embed(
                        title="✅ Star Tier List | Unban", 
                        description=f"**{nick}** adlı oyuncunun hile cezası bitti. / The ban duration for **{nick}** has expired.\n*Hileli rolü otomatik olarak kaldırıldı.*", 
                        color=discord.Color.green()
                    )
                    embed.set_thumbnail(url=f"https://visage.surgeplay.com/face/512/{gorsel_uuid}")
                    embed.add_field(name="📋 Kayıt ID / Record ID", value=f"`{islem_id}`", inline=True)
                    await kanal.send(content=f"<@{d_id}>", embed=embed)
            
            cursor.execute("DELETE FROM hile_listesi WHERE bitis_tarihi <= CURRENT_TIMESTAMP")
            conn.commit()
        conn.close()

    @hile_suresi_kontrol.before_loop
    async def before_hile_kontrol(self):
        await self.wait_until_ready()

bot = UltimateBot()

def sadece_sahip():
    def predicate(interaction: discord.Interaction) -> bool:
        return interaction.user.id in SAHIP_IDLER
    return app_commands.check(predicate)


# ================= UI SİSTEMLERİ =================
class WaitlistModal(discord.ui.Modal, title="Star Tier List | Form"):
    def __init__(self, secilen_kit):
        super().__init__(timeout=None)
        self.secilen_kit = secilen_kit.lower()

    region_input = discord.ui.TextInput(
        label="Region (TR / EU)", 
        style=discord.TextStyle.short, 
        placeholder="TR or EU...", 
        required=True, 
        max_length=10
    )
    
    nick_input = discord.ui.TextInput(
        label="Minecraft Nick", 
        style=discord.TextStyle.short, 
        placeholder="Your in-game name...", 
        required=True, 
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        
        if user_id not in WAITLIST_USERS:
            WAITLIST_USERS[user_id] = {"isim": self.nick_input.value, "bolge": self.region_input.value, "kitler": []}
        else:
            WAITLIST_USERS[user_id]["isim"] = self.nick_input.value
            WAITLIST_USERS[user_id]["bolge"] = self.region_input.value
            
        if self.secilen_kit not in WAITLIST_USERS[user_id]["kitler"]:
            WAITLIST_USERS[user_id]["kitler"].append(self.secilen_kit)
        
        bilgi_mesaji = f"✅ **Başvuru Alındı! / Application Received!**\nSeçtiğiniz Kit / Chosen Kit: **{self.secilen_kit.capitalize()}**"
        rol_id = AYARLAR.get("kit_bekleme_rolleri", {}).get(self.secilen_kit)
        
        if rol_id:
            role = interaction.guild.get_role(rol_id)
            if role:
                try: 
                    await interaction.user.add_roles(role)
                    bilgi_mesaji += f"\n🎯 Size **{role.name}** rolü verildi! / Role assigned!"
                except: 
                    pass

        kanal = discord.utils.get(interaction.guild.text_channels, name=f"{self.secilen_kit}-waitlist")
        kanal_mention = kanal.mention if kanal else f"**#{self.secilen_kit}-waitlist**"
        bilgi_mesaji += f"\nLütfen {kanal_mention} kanalına gidip **Sıraya Katıl (Join Queue)** butonuna basın."
        await interaction.response.send_message(bilgi_mesaji, ephemeral=True)

class KitSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for kit in KITLER:
            emoji_str = get_kit_emoji(kit)
            try: 
                emoji_obj = discord.PartialEmoji.from_str(emoji_str)
            except: 
                emoji_obj = emoji_str
            options.append(discord.SelectOption(label=kit, value=kit.lower(), emoji=emoji_obj))
            
        super().__init__(
            placeholder="Choose a kit / Test olmak istediğiniz kiti seçin...", 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id="kit_select_menu", 
            row=0
        )

    async def callback(self, interaction: discord.Interaction):
        if hile_kontrol(interaction):
            return await interaction.response.send_message("❌ **Hile listesindesiniz! / You are blacklisted!**", ephemeral=True)
            
        secilen_kit = self.values[0]
        user_id = interaction.user.id
        
        conn = sqlite3.connect("tierlist.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tarih FROM oyuncular WHERE discord_id = ? AND kit COLLATE NOCASE = ?", (user_id, secilen_kit))
        kayit = cursor.fetchone()
        conn.close()

        is_booster = interaction.user.premium_since is not None

        if kayit:
            son_test_tarihi = datetime.datetime.strptime(kayit[0], '%Y-%m-%d %H:%M:%S')
            gecen_zaman = datetime.datetime.utcnow() - son_test_tarihi
            
            cooldown_days = 3 if is_booster else 5
            
            if gecen_zaman.total_seconds() < cooldown_days * 86400:
                kalan_saniye = (cooldown_days * 86400) - gecen_zaman.total_seconds()
                kalan_gun = int(kalan_saniye // 86400)
                kalan_saat = int((kalan_saniye % 86400) // 3600)
                kalan_dakika = int((kalan_saniye % 3600) // 60)
                
                mesaj = f"❌ **Cooldown!** Şu an **{secilen_kit.capitalize()}** kiti için teste giremezsin.\n"
                mesaj += f"⏱️ Bekleme sürenin bitmesine **{kalan_gun} gün, {kalan_saat} saat, {kalan_dakika} dakika** kaldı.\n"
                
                if not is_booster:
                    mesaj += "\n🚀 *(Sunucuya **Boost** basarak bekleme süreni 5 günden 3 güne düşürebilir ve hemen teste girebilirsin!)*"
                    
                return await interaction.response.send_message(mesaj, ephemeral=True)

        await interaction.response.send_modal(WaitlistModal(self.values[0]))

class MainWaitlistView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(KitSelect())
        
        btn_kurallar = discord.ui.Button(
            label="Kurallar / Rules", 
            style=discord.ButtonStyle.secondary, 
            emoji="📜", 
            custom_id="kurallar_btn", 
            row=1
        )
        btn_kurallar.callback = self.kurallar_callback
        self.add_item(btn_kurallar)
        
        btn_cooldown = discord.ui.Button(
            label="Cooldown", 
            style=discord.ButtonStyle.primary, 
            emoji="⏱️", 
            custom_id="cooldown_btn", 
            row=1
        )
        btn_cooldown.callback = self.cooldown_callback
        self.add_item(btn_cooldown)

    async def kurallar_callback(self, interaction: discord.Interaction):
        kurallar_metni = """
**📖 Kurallar / Rules**
• Bir oyuncu, değerlendirme testleri sonucunda en fazla LT3 alabilir.
• Testler, oyuncu ve testerin ortak kararıyla belirlenen sunucuda yapılır.
• Tester’i veya testi trollemek kesinlikle yasaktır.
• Testi kasıtlı olarak uzatmanız durumunda (tester’dan kaçma vb.), tester testi sonlandırma hakkına sahiptir.
• Yan hesap ile teste girmek cezaya tabidir.
• Kendi yerinize başka bir oyuncuyu teste sokmanız, ceza almanıza neden olur.

**📝 Terimler / Terminology**
• **HT (High Tier):** Yüksek seviye. / High Level. (Örnek: HT3)
• **LT (Low Tier):** Düşük seviye. / Low Level. (Örnek: LT3)
• **FT (First To):** Maç / round sistemi. / Match system. (Örnek: FT2 = 2 round kazanan maçı kazanır)

**✅ İzin Verilen Modlar / Allowed Mods**
• Performans / PvP modları
• Armor HUD, Potion HUD
• Dayanıklılık (Durability) gösteren Texture Pack’ler
• Can (Health) gösteren modlar

**❌ İzin Verilmeyen Modlar / Disallowed Mods**
• Hack Client’ler, Mouse Tweaks, Item Scroller, Macro, Inventory Profiles Next, Regedit / SnapTap, Crystal Click, Double Bind

**⛔ Hile & Blacklist Süreleri / Ban Durations**
• Auto Clicker: 1 - 3 Ay / Months
• Yasaklı Modlar / Forbidden Mods: 1 Ay / Month
• Hile Client’ler / Hack Clients: 3 Ay / Months
• Kontrol Reddi / Refusing SS: 3 Ay / Months
• Tier Boosting: Süresiz (Kalıcı) / Permanent
• Ortak Premium Kullanımı / Account Sharing: Kalıcı Blacklist / Permanent
• Discord’da yan hesapla teste girmek / Alt account testing: Blacklist

**🔥 High-Test Cooldown**
• Normal Cooldown: **15 Gün/Days** | Boost Basarak / With Boost: **7 Gün/Days**

**⏱️ Normal Cooldown**
• Normal Cooldown: **5 Gün/Days** | Boost Cooldown / With Boost: **3 Gün/Days**

**🏆 HT3 - Yüksek Test Geçme Skorları / HT3 Requirements**
• **Nethpot:** Eval’leri en az 4–2 skorla geçmeli ve HT3’ten en az 3 sayı almalıdır. (FT4)
• **Pot, Sword, Axe, UHC:** Eval’leri en az 10–6 skorla geçmeli ve HT3’ten en az 8 sayı almalıdır. (FT10)
• **SMP, DiaSMP, Mace:** Eval’leri en az 4–2 skorla geçmeli ve HT3’ten en az 3 sayı almalıdır. (FT4)
• **Crystal:** Eval’leri en az 3–1 skorla geçmeli ve HT3’ten en az 3 sayı almalıdır. (FT3)

**🥈 LT2 - Yüksek Test Geçme Skorları / LT2 Requirements**
• **Nethpot, SMP, DiaSMP, Mace:** 2 adet HT3’ü, her birine en az 2 sayı vererek geçmeli ve LT2’den en az 3 puan almalıdır. (FT4)
• **Pot, Sword, UHC:** 2 adet HT3’ü, her birine en az 6 sayı vererek geçmeli ve LT2’den en az 8 puan almalıdır. (FT10)
• **Axe:** 2 adet HT3’ü, her birine en az 10 sayı vererek geçmeli ve LT2’den en az 13 puan almalıdır. (FT15)
• **Crystal:** 2 adet HT3 yenilmelidir. Ayrıca 2 adet LT2 ile savaşılması gerekir. HT3’lere karşı galip gelinmeli, LT2’lere karşı ise toplam 7 tur kazanılmalıdır.

**⚔️ Testler Kaç FT? / FT Settings**
• **Nethpot, SMP, DiaSMP, Mace:** FT2 — (HT3) High-Test: FT4
• **Pot, UHC:** FT4 — (HT3) High-Test: FT10
• **Sword:** FT5 — (HT3) High-Test: FT10
• **Axe:** FT7 — (HT3) High-Test: FT10
• **Crystal:** FT3 — (HT3) High-Test: FT4
        """
        embed = discord.Embed(title="Star Tier List | Rules & Evaluation", description=kurallar_metni, color=discord.Color.dark_theme())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def cooldown_callback(self, interaction: discord.Interaction):
        conn = sqlite3.connect("tierlist.db")
        cursor = conn.cursor()
        cursor.execute("SELECT kit, tarih FROM oyuncular WHERE discord_id = ?", (interaction.user.id,))
        kayitlar = cursor.fetchall()
        conn.close()

        if not kayitlar:
            return await interaction.response.send_message("Henüz hiçbir test sonucunuz bulunmuyor. Cooldown süreniz yok! 🟢", ephemeral=True)

        is_booster = interaction.user.premium_since is not None
        cooldown_days = 3 if is_booster else 5
        now = datetime.datetime.utcnow()

        mesaj = f"⏱️ **{interaction.user.display_name} Cooldown Durumu**\n"
        mesaj += f"*(Sizin Bekleme Süreniz: {cooldown_days} Gün)*\n\n"

        for kit, tarih_str in kayitlar:
            son_test_tarihi = datetime.datetime.strptime(tarih_str, '%Y-%m-%d %H:%M:%S')
            gecen_zaman = now - son_test_tarihi
            
            if gecen_zaman.total_seconds() < cooldown_days * 86400:
                kalan_saniye = (cooldown_days * 86400) - gecen_zaman.total_seconds()
                kalan_gun = int(kalan_saniye // 86400)
                kalan_saat = int((kalan_saniye % 86400) // 3600)
                mesaj += f"🔴 **{kit.capitalize()}**: ⏳ {kalan_gun} gün {kalan_saat} saat kaldı. *(Test zamanı: {gecen_zaman.days} gün önce)*\n"
            else:
                mesaj += f"🟢 **{kit.capitalize()}**: Hazır! ✅ *(Test zamanı: {gecen_zaman.days} gün önce)*\n"

        await interaction.response.send_message(mesaj, ephemeral=True)


async def process_queue(guild, kit_adi):
    queue = QUEUES[kit_adi]
    while AKTIF_TEST_SAYISI[kit_adi] < len(ACTIVE_TESTERS[kit_adi]) and len(queue) > 0:
        user_id = queue.pop(0)
        user = guild.get_member(user_id)
        if not user: continue
        
        AKTIF_TEST_SAYISI[kit_adi] += 1
            
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False), 
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True), 
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for role_id in KIT_ROLLER.get(kit_adi, []):
            role = guild.get_role(role_id)
            if role: 
                overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
                
        ticket_kanali = await guild.create_text_channel(f"test-{user.name}", overwrites=overwrites)
        user_data = WAITLIST_USERS.get(user.id, {"isim": "Unknown", "bolge": "Unknown"})
        
        embed = discord.Embed(
            title="Star Tier List | Session Started", 
            description=f"{user.mention}, **{kit_adi.capitalize()}** kiti için sıranız geldi! / It is your turn!", 
            color=discord.Color.green()
        )
        embed.add_field(name="Minecraft Nick", value=user_data["isim"], inline=True)
        embed.add_field(name="Region", value=user_data["bolge"], inline=True)
        
        await ticket_kanali.send(f"{user.mention}", embed=embed, view=CloseTicketView(kit_adi))
        
        if QUEUE_MESSAGES[kit_adi]: 
            await update_queue_message(QUEUE_MESSAGES[kit_adi].channel, kit_adi, ping_everyone=False)

class CloseTicketView(discord.ui.View):
    def __init__(self, kit_adi):
        super().__init__(timeout=None)
        self.kit_adi = kit_adi.lower()
        
    @discord.ui.button(label="Bileti Kapat / Close Ticket", style=discord.ButtonStyle.danger, custom_id="close_btn")
    async def close_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage_kit(interaction.user, self.kit_adi): 
            return await interaction.response.send_message("❌ Yetkiniz yok! / No permission!", ephemeral=True)
            
        AKTIF_TEST_SAYISI[self.kit_adi] = max(0, AKTIF_TEST_SAYISI[self.kit_adi] - 1)
        await interaction.response.send_message("Kapatılıyor... / Closing...", ephemeral=True)
        await interaction.channel.delete() 
        await process_queue(interaction.guild, self.kit_adi)

class QueueView(discord.ui.View):
    def __init__(self, kit_adi):
        super().__init__(timeout=None)
        self.kit_adi = kit_adi.lower()

    @discord.ui.button(label="Sıraya Katıl / Join Queue", style=discord.ButtonStyle.primary, custom_id="join_btn")
    async def join_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if hile_kontrol(interaction):
            return await interaction.response.send_message("❌ **Hile listesinde olduğunuz için sıralara giremezsiniz! / You are blacklisted!**", ephemeral=True)
            
        user_id = interaction.user.id
        if user_id not in WAITLIST_USERS or self.kit_adi not in WAITLIST_USERS[user_id].get("kitler", []): 
            return await interaction.response.send_message("❌ Önce ana panelden formu doldurun! / Please fill the form first!", ephemeral=True)
        
        if len(ACTIVE_TESTERS[self.kit_adi]) == 0: 
            return await interaction.response.send_message("Şu an aktif tester yok! / No active testers!", ephemeral=True)
            
        if user_id in QUEUES[self.kit_adi]: 
            return await interaction.response.send_message("Zaten sıradasınız! / You are already in the queue!", ephemeral=True)

        conn = sqlite3.connect("tierlist.db")
        cursor = conn.cursor()
        cursor.execute("SELECT tarih FROM oyuncular WHERE discord_id = ? AND kit COLLATE NOCASE = ?", (user_id, self.kit_adi))
        kayit = cursor.fetchone()
        conn.close()

        user = interaction.guild.get_member(user_id)
        is_booster = user and user.premium_since is not None

        if kayit:
            son_test_tarihi = datetime.datetime.strptime(kayit[0], '%Y-%m-%d %H:%M:%S')
            gecen_zaman = datetime.datetime.utcnow() - son_test_tarihi
            cooldown_days = 3 if is_booster else 5
            
            if gecen_zaman.total_seconds() < cooldown_days * 86400:
                kalan_saniye = (cooldown_days * 86400) - gecen_zaman.total_seconds()
                kalan_gun = int(kalan_saniye // 86400)
                kalan_saat = int((kalan_saniye % 86400) // 3600)
                
                hata_mesaji = f"❌ **Cooldown!** {self.kit_adi.capitalize()} kitinde test olmak için bekleme süreniz dolmadı.\n"
                hata_mesaji += f"⏱️ Kalan Süre: **{kalan_gun} gün, {kalan_saat} saat**."
                
                return await interaction.response.send_message(hata_mesaji, ephemeral=True)

        if is_booster:
            insert_idx = len(QUEUES[self.kit_adi])
            for i, uid in enumerate(QUEUES[self.kit_adi]):
                member = interaction.guild.get_member(uid)
                if member and member.premium_since is None:
                    insert_idx = i
                    break
            QUEUES[self.kit_adi].insert(insert_idx, user_id)
            await interaction.response.send_message("✅ Sıraya katıldınız! (⭐ Booster Önceliği kullanıldı! / Booster Priority applied!)", ephemeral=True)
        else:
            QUEUES[self.kit_adi].append(user_id)
            await interaction.response.send_message("✅ Sıraya katıldınız! / Joined the queue!", ephemeral=True)
            
        await update_queue_message(interaction.channel, self.kit_adi, ping_everyone=False)
        await process_queue(interaction.guild, self.kit_adi)

    @discord.ui.button(label="Ayrıl / Leave", style=discord.ButtonStyle.secondary, custom_id="leave_btn")
    async def leave_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        if user_id in QUEUES[self.kit_adi]:
            QUEUES[self.kit_adi].remove(user_id)
            await interaction.response.send_message("Sıradan ayrıldınız. / Left the queue.", ephemeral=True)
            await update_queue_message(interaction.channel, self.kit_adi)
            
            role = interaction.guild.get_role(AYARLAR.get("kit_bekleme_rolleri", {}).get(self.kit_adi))
            if role:
                try: 
                    await interaction.user.remove_roles(role)
                except: 
                    pass
                    
            if self.kit_adi in WAITLIST_USERS.get(user_id, {}).get("kitler", []): 
                WAITLIST_USERS[user_id]["kitler"].remove(self.kit_adi)
        else: 
            await interaction.response.send_message("Sırada değilsiniz! / You are not in the queue!", ephemeral=True)


async def update_queue_message(channel, kit_adi, ping_everyone=False):
    global QUEUE_MESSAGES
    queue = QUEUES[kit_adi]
    
    if len(ACTIVE_TESTERS[kit_adi]) == 0:
        mesaj_icerigi = None
        embed = discord.Embed(
            title=f"Star Tier List | {kit_adi.capitalize()} Queue", 
            description="Şu an aktif tester bulunmuyor. / No testers online.", 
            color=discord.Color.dark_theme()
        )
        view = None
    else:
        mesaj_icerigi = "@here 🟢 **Kuyruk Açıldı! Test olmak isteyenler butona tıklayıp sıraya girebilir!**" if ping_everyone else None
        
        embed = discord.Embed(
            title=f"Star Tier List | {kit_adi.capitalize()} Queue", 
            description="⏱️ Sıra otomatik güncellenir. / Auto-updates.", 
            color=discord.Color.dark_theme()
        )
        
        queue_text = ""
        for i, uid in enumerate(queue):
            member = channel.guild.get_member(uid)
            if member:
                queue_text += f"{i+1}. {member.mention}\n"
                
        if not queue_text:
            queue_text = "Sıra boş. / Queue is empty."
            
        embed.add_field(name=f"**Sıra / Queue** ({len(queue)}/20):", value=queue_text, inline=False)
        
        tester_text = ""
        for i, tester in enumerate(ACTIVE_TESTERS[kit_adi]):
            tester_text += f"{i+1}. {tester.mention}\n"
            
        if not tester_text:
            tester_text = "Yok / None"
            
        embed.add_field(name="**Aktif Testerlar / Active Testers:**", value=tester_text, inline=False)
        view = QueueView(kit_adi)

    if QUEUE_MESSAGES[kit_adi] is None:
        QUEUE_MESSAGES[kit_adi] = await channel.send(content=mesaj_icerigi, embed=embed, view=view)
    else:
        try:
            await QUEUE_MESSAGES[kit_adi].edit(content=mesaj_icerigi, embed=embed, view=view)
        except discord.errors.NotFound:
            QUEUE_MESSAGES[kit_adi] = await channel.send(content=mesaj_icerigi, embed=embed, view=view)

class TesterActionView(discord.ui.View):
    def __init__(self, kit_adi):
        super().__init__(timeout=None)
        self.kit_adi = kit_adi.lower()
        
    @discord.ui.button(label="🟢 Testi Aç / Open", style=discord.ButtonStyle.success, custom_id="test_ac_btn")
    async def ac_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage_kit(interaction.user, self.kit_adi): 
            return await interaction.response.send_message("❌ Yetkiniz yok! / No permission!", ephemeral=True)
        
        global AKTIF_TEST_SAYISI
        ilk_kez_aciliyor = len(ACTIVE_TESTERS[self.kit_adi]) == 0
        
        if ilk_kez_aciliyor: 
            QUEUES[self.kit_adi].clear()
            AKTIF_TEST_SAYISI[self.kit_adi] = 0
            
        if interaction.user not in ACTIVE_TESTERS[self.kit_adi]:
            ACTIVE_TESTERS[self.kit_adi].append(interaction.user)
            await interaction.response.send_message(f"✅ **{self.kit_adi.capitalize()}** testerı oldunuz! / Tester status active!", ephemeral=True)
            
            if QUEUE_MESSAGES[self.kit_adi]: 
                await update_queue_message(QUEUE_MESSAGES[self.kit_adi].channel, self.kit_adi, ping_everyone=ilk_kez_aciliyor)
                
            await process_queue(interaction.guild, self.kit_adi)
        else: 
            await interaction.response.send_message("❌ Zaten aktifsiniz! / Already active!", ephemeral=True)

    @discord.ui.button(label="🔴 Testi Kapat / Close", style=discord.ButtonStyle.danger, custom_id="test_kapat_btn")
    async def kapat_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not can_manage_kit(interaction.user, self.kit_adi): 
            return await interaction.response.send_message("❌ Yetkiniz yok! / No permission!", ephemeral=True)
            
        if interaction.user in ACTIVE_TESTERS[self.kit_adi]:
            ACTIVE_TESTERS[self.kit_adi].remove(interaction.user)
            await interaction.response.send_message("✅ Çıktınız! / Status inactive!", ephemeral=True)
            
            if len(ACTIVE_TESTERS[self.kit_adi]) == 0: 
                QUEUES[self.kit_adi].clear()
                AKTIF_TEST_SAYISI[self.kit_adi] = 0
                
            if QUEUE_MESSAGES[self.kit_adi]: 
                await update_queue_message(QUEUE_MESSAGES[self.kit_adi].channel, self.kit_adi, ping_everyone=False)
        else: 
            await interaction.response.send_message("❌ Aktif değilsiniz! / Not active!", ephemeral=True)

class ControlPanelSelect(discord.ui.Select):
    def __init__(self):
        options = []
        for kit in KITLER:
            emoji_str = get_kit_emoji(kit)
            try:
                if emoji_str.startswith("<"):
                    emoji_obj = discord.PartialEmoji.from_str(emoji_str)
                else:
                    emoji_obj = emoji_str
            except:
                emoji_obj = "🎮"
            
            options.append(discord.SelectOption(label=kit, value=kit.lower(), emoji=emoji_obj))
            
        super().__init__(
            placeholder="Yönetmek istediğiniz kiti seçin / Select kit to manage...", 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id="control_panel_select"
        )

    async def callback(self, interaction: discord.Interaction):
        if not can_manage_kit(interaction.user, self.values[0]): 
            return await interaction.response.send_message("❌ Yetkiniz yok! / No permission!", ephemeral=True)
            
        embed = discord.Embed(
            title="Star Tier List | Control Panel", 
            description="Sırayı yönetin / Manage the queue.", 
            color=discord.Color.gold()
        )
        
        await interaction.response.send_message(
            embed=embed, 
            view=TesterActionView(self.values[0]), 
            ephemeral=True
        )

class MainControlPanelView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ControlPanelSelect())


# ================= GİZLİ KURULUM VE AYAR KOMUTLARI =================
@bot.tree.command(name="kur_ana_panel", description="TR/EN: Ana başvuru panelini kurar. / Sets up the main apply panel.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def kur_ana_panel(interaction: discord.Interaction):
    await interaction.response.send_message("Panel Kuruldu / Panel Setup Complete.", ephemeral=True)
    embed_aciklamasi = (
        "**Hangi kitte test olmak istersin? / Which kit do you want to test in?** ⚔️\n\n"
        "📜 Aşağıdan waitliste katılmak istediğin kiti seçebilirsin.\n"
        "📜 Select the kit you want to join the waitlist for from below.\n\n"
        "---\n\n"
        "🟢 **Bekleme Süresi (Cooldown)**\n"
        "• Normal: **5 gün / days**\n"
        "• Sunucuya **Boost** basarak / By Boosting: **3 gün / days**\n\n"
        "🟢 **Öncelik Sistemi (Priority System)**\n"
        "• ⭐ **Booster kullanıcılar sıraya katıldıklarında otomatik olarak sıranın en başına alınır!**\n"
        "• ⭐ **Boosters are automatically moved to the front of the queue!**"
    )
    panel_embed = discord.Embed(title="Star Tier List", description=embed_aciklamasi, color=discord.Color.from_rgb(43, 45, 49))
    await interaction.channel.send(embed=panel_embed, view=MainWaitlistView())

@bot.tree.command(name="kur_sira_paneli", description="TR/EN: Sıra panelini kurar. / Sets up the queue panel.")
@app_commands.choices(kit=[app_commands.Choice(name=k, value=k) for k in KITLER])
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def kur_sira_paneli(interaction: discord.Interaction, kit: app_commands.Choice[str]):
    QUEUE_MESSAGES[kit.value.lower()] = None 
    await interaction.response.send_message("Başlatılıyor... / Starting...", ephemeral=True)
    await update_queue_message(interaction.channel, kit.value.lower(), ping_everyone=False)

@bot.tree.command(name="kur_kontrol_paneli", description="TR/EN: Tester Kontrol Panelini kurar. / Sets up Control Panel.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def kur_kontrol_paneli(interaction: discord.Interaction):
    await interaction.response.send_message("Kuruldu. / Setup complete.", ephemeral=True)
    
    embed = discord.Embed(
        title="Star Tier List | Tester Panel", 
        description="Kiti seçin. / Select the kit.", 
        color=discord.Color.dark_grey()
    )
    await interaction.channel.send(embed=embed, view=MainControlPanelView())

@bot.tree.command(name="emojileri_otomatik_bul", description="TR: Sunucudaki kit emojilerini tarar.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def emojileri_otomatik_bul(interaction: discord.Interaction):
    bulunanlar = 0
    eslesme = {
        "nethpot": ["nethop", "nethpot"], 
        "sword": ["sword"], 
        "axe": ["axe"], 
        "smp": ["smp"], 
        "diasmp": ["diasmp", "dia smp"], 
        "mace": ["mace"], 
        "pot": ["pot"], 
        "uhc": ["uhc"], 
        "crystal": ["crystal"]
    }
    
    if "emojiler" not in AYARLAR: 
        AYARLAR["emojiler"] = {}
        
    for kit, isimler in eslesme.items():
        for emoji in interaction.guild.emojis:
            if emoji.name.lower() in isimler:
                AYARLAR["emojiler"][kit] = str(emoji)
                bulunanlar += 1
                break
                
    ayarlari_kaydet(AYARLAR)
    await interaction.response.send_message(f"✅ Bulunan emoji: {bulunanlar}", ephemeral=True)

@bot.tree.command(name="kit_bekleme_rol_ata", description="TR: Kit bekleme rolünü ayarlar.")
@app_commands.choices(kit=[app_commands.Choice(name=k, value=k) for k in KITLER])
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def kit_bekleme_rol_ata(interaction: discord.Interaction, kit: app_commands.Choice[str], rol: discord.Role):
    if "kit_bekleme_rolleri" not in AYARLAR: 
        AYARLAR["kit_bekleme_rolleri"] = {}
        
    AYARLAR["kit_bekleme_rolleri"][kit.value.lower()] = rol.id
    ayarlari_kaydet(AYARLAR)
    await interaction.response.send_message("✅ Başarılı.", ephemeral=True)

@bot.tree.command(name="hile_rol_ayarla", description="TR: Blacklist rolünü seçer.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def hile_rol_ayarla(interaction: discord.Interaction, rol: discord.Role):
    AYARLAR["hile_rolu"] = rol.id
    ayarlari_kaydet(AYARLAR)
    await interaction.response.send_message(f"✅ Başarılı! Hilecilere **{rol.name}** verilecek.", ephemeral=True)

@bot.tree.command(name="hile_bildirim_rol", description="TR: Ban loglarında etiketlenecek rolü ayarlar. / EN: Sets ping role for bans.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def hile_bildirim_rol(interaction: discord.Interaction, rol: discord.Role):
    conn = sqlite3.connect("tierlist.db")
    conn.execute("REPLACE INTO ayarlar (ayar_adi, deger) VALUES (?, ?)", ("hile_bildirim_rolu", str(rol.id)))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Ayarlandı. Hile loglarında {rol.mention} etiketlenecek.", ephemeral=True)

@bot.tree.command(name="tier_kanali_ayarla", description="TR: Tier sonuç kanalını seçer.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def tier_kanali_ayarla(interaction: discord.Interaction, kanal: discord.TextChannel):
    conn = sqlite3.connect("tierlist.db")
    conn.execute("REPLACE INTO ayarlar (ayar_adi, deger) VALUES (?, ?)", ("tier_kanali", str(kanal.id)))
    conn.commit()
    conn.close()
    await interaction.response.send_message("✅ Ayarlandı.", ephemeral=True)

@bot.tree.command(name="hile_kanal_ayarla", description="TR: Ban/Unban loglarının gönderileceği kanalı ayarlar.")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def hile_kanal_ayarla(interaction: discord.Interaction, kanal: discord.TextChannel):
    conn = sqlite3.connect("tierlist.db")
    conn.execute("REPLACE INTO ayarlar (ayar_adi, deger) VALUES (?, ?)", ("hile_kanali", str(kanal.id)))
    conn.commit()
    conn.close()
    await interaction.response.send_message(f"✅ Ayarlandı. Loglar {kanal.mention} kanalına gidecek.", ephemeral=True)

@bot.tree.command(name="tester_rol_ekle", description="TR: Bir ROLÜN testleri yönetmesine izin verir.")
@app_commands.choices(kit=[app_commands.Choice(name=k, value=k) for k in KITLER])
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def tester_rol_ekle(interaction: discord.Interaction, kit: app_commands.Choice[str], rol: discord.Role):
    k_lower = kit.value.lower()
    
    if rol.id not in KIT_ROLLER[k_lower]:
        KIT_ROLLER[k_lower].append(rol.id)
        rolleri_kaydet(KIT_ROLLER)
        await interaction.response.send_message(f"✅ **{rol.name}** eklendi!")
    else: 
        await interaction.response.send_message("❌ Zaten var.", ephemeral=True)

@bot.tree.command(name="tier_kaldir", description="TR: Bir oyuncunun belirli bir kitteki tierini siler.")
@app_commands.choices(kit=[app_commands.Choice(name=k, value=k) for k in KITLER])
@app_commands.default_permissions(administrator=True)
async def tier_kaldir(interaction: discord.Interaction, nick: str, kit: app_commands.Choice[str]):
    await tier_kaldir_merkezi(interaction, nick, kit.value)

@bot.tree.command(name="remove_tier", description="EN: Removes a player's tier from a specific kit.")
@app_commands.choices(kit=[app_commands.Choice(name=k, value=k) for k in KITLER])
@app_commands.default_permissions(administrator=True)
async def remove_tier(interaction: discord.Interaction, nick: str, kit: app_commands.Choice[str]):
    await tier_kaldir_merkezi(interaction, nick, kit.value)

@bot.tree.command(name="tester_cikart", description="TR: Belirtilen kitteki bir tester'ı aktif listeden çıkartır. (Sadece Yönetici)")
@app_commands.choices(kit=[app_commands.Choice(name=k, value=k) for k in KITLER])
@app_commands.default_permissions(administrator=True)
async def tester_cikart(interaction: discord.Interaction, kit: app_commands.Choice[str], tester: discord.Member):
    kit_adi = kit.value.lower()
    
    if tester in ACTIVE_TESTERS[kit_adi]:
        ACTIVE_TESTERS[kit_adi].remove(tester)
        await interaction.response.send_message(f"✅ {tester.mention}, **{kit.value}** kiti tester listesinden zorla çıkartıldı.", ephemeral=True)
        
        if len(ACTIVE_TESTERS[kit_adi]) == 0: 
            QUEUES[kit_adi].clear()
            AKTIF_TEST_SAYISI[kit_adi] = 0
            
        if QUEUE_MESSAGES[kit_adi]: 
            await update_queue_message(QUEUE_MESSAGES[kit_adi].channel, kit_adi, ping_everyone=False)
    else:
        await interaction.response.send_message(f"❌ {tester.mention} şu an **{kit.value}** kitinde aktif tester değil.", ephemeral=True)

# YENİ EKLENEN AF/UNBAN KOMUTU
@bot.tree.command(name="hile_kaldir", description="TR: Bir oyuncunun hile (blacklist) cezasını manuel olarak kaldırır. (Sadece Patron)")
@app_commands.describe(nick="Cezası kaldırılacak oyuncunun Minecraft nicki")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def hile_kaldir(interaction: discord.Interaction, nick: str):
    await interaction.response.defer(ephemeral=True)

    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()

    cursor.execute("SELECT discord_id, kayit_id FROM hile_listesi WHERE minecraft_nick COLLATE NOCASE = ?", (nick,))
    kayit = cursor.fetchone()

    if not kayit:
        conn.close()
        return await interaction.followup.send(f"❌ `{nick}` adında blacklist'te olan bir oyuncu bulunamadı.")

    discord_id = kayit[0]
    kayit_id = kayit[1]

    cursor.execute("DELETE FROM hile_listesi WHERE minecraft_nick COLLATE NOCASE = ?", (nick,))
    conn.commit()

    kullanici = interaction.guild.get_member(discord_id)
    if kullanici:
        hile_rol_id = AYARLAR.get("hile_rolu")
        if hile_rol_id:
            hile_rol = interaction.guild.get_role(hile_rol_id)
            if hile_rol and hile_rol in kullanici.roles:
                try: 
                    await kullanici.remove_roles(hile_rol)
                except: 
                    pass

    embed = discord.Embed(
        title="✅ Star Tier List | Unban (Manuel)",
        description=f"**{nick}** adlı oyuncunun hile cezası {interaction.user.mention} tarafından kaldırıldı.\n*Eğer sunucudaysa hileli rolü alındı.*",
        color=discord.Color.green()
    )
    embed.add_field(name="📋 Kayıt ID", value=f"`{kayit_id}`", inline=True)

    await interaction.followup.send(embed=embed)

    cursor.execute("SELECT deger FROM ayarlar WHERE ayar_adi = 'hile_kanali'")
    kanal_ayari = cursor.fetchone()
    conn.close()

    if kanal_ayari:
        log_kanal = interaction.guild.get_channel(int(kanal_ayari[0]))
        if log_kanal:
            await log_kanal.send(embed=embed)


# ================= AÇIK SİSTEM KOMUTLARI (HERKESE AÇIK) =================

async def hile_islem_merkezi(interaction, kullanici, nick, sebep, sure_ay, kanit):
    has_aac = False
    if isinstance(interaction.user, discord.Member):
        has_aac = any(role.id == AAC_ROLE_ID for role in interaction.user.roles)
        
    if not is_tester(interaction.user) and not has_aac:
        return await interaction.response.send_message("❌ Bu komutu sadece yetkili Testerlar veya AAC Ekibi kullanabilir! / Tester or AAC only command!", ephemeral=True)

    await interaction.response.defer()

    hile_rol_id = AYARLAR.get("hile_rolu")
    if hile_rol_id:
        hile_rol = interaction.guild.get_role(hile_rol_id)
        if hile_rol:
            try: 
                await kullanici.add_roles(hile_rol)
            except: 
                pass
            
    for r_id in list(AYARLAR.get("kit_bekleme_rolleri", {}).values()):
        role = interaction.guild.get_role(r_id)
        if role and role in kullanici.roles:
            try: 
                await kullanici.remove_roles(role)
            except: 
                pass
            
    for k in KITLER:
        k_lower = k.lower()
        if kullanici.id in QUEUES[k_lower]:
            QUEUES[k_lower].remove(kullanici.id)
            if QUEUE_MESSAGES[k_lower]: 
                await update_queue_message(QUEUE_MESSAGES[k_lower].channel, k_lower)
            
    if kullanici.id in WAITLIST_USERS:
        del WAITLIST_USERS[kullanici.id]

    islem_id = f"HL{random.randint(1000000000, 9999999999)}"
    bitis_tarihi = datetime.datetime.now() + datetime.timedelta(days=sure_ay * 30)

    uuid = await minecraft_uuid_al(nick)
    gorsel_uuid = uuid or STEVE_UUID
    kayit_uuid = uuid or "non-premium"
    
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM oyuncular WHERE discord_id = ? OR minecraft_nick = ?", (kullanici.id, nick))
    silinen_sayi = cursor.rowcount

    tierlist_bilgi = f"`{nick}` kayıt bulunamadı. / No tierlist record found."
    if silinen_sayi > 0: 
        tierlist_bilgi = f"**{silinen_sayi} adet tierlist kaydı silindi. / records deleted.**"

    kanit_url = kanit.url if kanit else ""
    cursor.execute(
        "INSERT INTO hile_listesi (kayit_id, discord_id, minecraft_nick, sebep, sure_ay, bitis_tarihi, yonetici_id, kanit_url, uuid) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (islem_id, kullanici.id, nick, sebep, sure_ay, bitis_tarihi.strftime('%Y-%m-%d %H:%M:%S'), interaction.user.id, kanit_url, kayit_uuid)
    )
    conn.commit()

    embed = discord.Embed(
        title="🚫 Star Tier List | Blacklisted", 
        description=f"{kullanici.mention} adlı oyuncu Blacklist'e eklendi. / Added to Blacklist.\n*Kuyruklardan atıldı ve Hileli rolü verildi.*", 
        color=discord.Color.from_rgb(255, 0, 0)
    )
    embed.set_thumbnail(url=f"https://visage.surgeplay.com/face/512/{gorsel_uuid}")
    embed.add_field(name="👤 Oyuncu / Player", value=f"• Discord: {kullanici.mention}\n• Nick: `{nick}`", inline=False)
    embed.add_field(name="🚨 Sebep / Reason", value=f"```\n- {sebep}\n```", inline=False)
    embed.add_field(name="⏳ Süre / Duration", value=f"• Süre: {sure_ay} Ay/Months\n• Bitiş/End: <t:{int(bitis_tarihi.timestamp())}:f>", inline=True)
    embed.add_field(name="ℹ️ Info", value=tierlist_bilgi, inline=False)
    
    if kanit_url: 
        embed.set_image(url=kanit_url)

    cursor.execute("SELECT deger FROM ayarlar WHERE ayar_adi = 'hile_kanali'")
    kanal_ayari = cursor.fetchone()
    
    cursor.execute("SELECT deger FROM ayarlar WHERE ayar_adi = 'hile_bildirim_rolu'")
    rol_ayari = cursor.fetchone()
    
    conn.close()

    if kanal_ayari:
        log_kanal = interaction.guild.get_channel(int(kanal_ayari[0]))
        if log_kanal:
            mesaj_icerigi = kullanici.mention
            if rol_ayari:
                mesaj_icerigi += f" <@&{rol_ayari[0]}>"
            await log_kanal.send(content=mesaj_icerigi, embed=embed)
            return await interaction.followup.send("✅ İşlem loglandı. / Logged.", ephemeral=True)

    await interaction.followup.send(embed=embed)


async def sonuc_islem_merkezi(interaction, nick, discord_kullanici, kit, tier, skor, sunucu):
    if not can_manage_kit(interaction.user, kit):
        return await interaction.response.send_message(f"❌ **{kit}** kiti için yetkiniz yok! / No permission for this kit!", ephemeral=True)

    await interaction.response.defer() 
    
    bekleme_rol_id = AYARLAR.get("kit_bekleme_rolleri", {}).get(kit.lower())
    if bekleme_rol_id:
        bekleme_rolu = interaction.guild.get_role(bekleme_rol_id)
        if bekleme_rolu and bekleme_rolu in discord_kullanici.roles:
            try: 
                await discord_kullanici.remove_roles(bekleme_rolu)
            except: 
                pass
    
    uuid = await minecraft_uuid_al(nick)
    gorsel_uuid = uuid or STEVE_UUID
    kayit_uuid = uuid or "non-premium"
    gorunen_nick = nick if uuid else f"{nick} (Non Premium)"

    uzun_yeni_tier = uzun_tier_ismi(tier)
    kit_emoji = get_kit_emoji(kit)

    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT klan FROM oyuncular WHERE minecraft_nick COLLATE NOCASE = ? AND klan IS NOT NULL", (nick,))
    klan_sorgu = cursor.fetchone()
    oyuncu_klani = klan_sorgu[0] if klan_sorgu else None

    cursor.execute("SELECT tier FROM oyuncular WHERE minecraft_nick = ? AND kit = ?", (nick, kit))
    eski_kayit = cursor.fetchone()
    
    eski_tier_kodu = None
    previous_rank_text = "Unranked / Derecesiz"
    
    if eski_kayit:
        eski_tier_kodu = eski_kayit[0]
        previous_rank_text = uzun_tier_ismi(eski_tier_kodu)
        cursor.execute(
            "UPDATE oyuncular SET tier = ?, uuid = ?, discord_id = ?, region = ?, tester_id = ?, skor = ?, klan = ?, tarih = CURRENT_TIMESTAMP WHERE minecraft_nick = ? AND kit = ?", 
            (tier, kayit_uuid, discord_kullanici.id, sunucu, interaction.user.id, skor, oyuncu_klani, nick, kit)
        )
    else:
        cursor.execute(
            "INSERT INTO oyuncular (minecraft_nick, uuid, discord_id, kit, tier, region, tester_id, skor, klan) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", 
            (nick, kayit_uuid, discord_kullanici.id, kit, tier, sunucu, interaction.user.id, skor, oyuncu_klani)
        )
    conn.commit()

    # Yeni rolü verme ve eskisi silme fonksiyonunu çalıştır
    await tier_rolu_guncelle(interaction.guild, discord_kullanici, kit, tier, eski_tier_kodu)

    aciklama = f"**Tester:**\n{interaction.user.mention}\n\n**Region:**\n{sunucu.upper()}\n\n**Kit:**\n{kit_emoji} {kit}\n\n**Player:**\n{gorunen_nick}\n\n**Score:**\n{skor}\n\n**Previous Tier:**\n{previous_rank_text}\n\n**New Tier:**\n{uzun_yeni_tier}"

    embed = discord.Embed(description=aciklama, color=discord.Color.red())
    embed.set_author(name=f"Star Tier List | {gorunen_nick} Result 🏆", icon_url=discord_kullanici.display_avatar.url)
    embed.set_thumbnail(url=f"https://visage.surgeplay.com/bust/512/{gorsel_uuid}")

    await interaction.followup.send(content=f"{discord_kullanici.mention} {interaction.user.mention}", embed=embed)

    cursor.execute("SELECT deger FROM ayarlar WHERE ayar_adi = 'tier_kanali'")
    kanal_ayari = cursor.fetchone()
    
    if kanal_ayari:
        log_kanali = interaction.guild.get_channel(int(kanal_ayari[0]))
        if log_kanali: 
            await log_kanali.send(content=f"🎉 Yeni test sonucu! / New evaluation! {discord_kullanici.mention}", embed=embed)
            
    conn.close()


async def tier_kaldir_merkezi(interaction, nick, kit):
    if not can_manage_kit(interaction.user, kit):
        return await interaction.response.send_message(f"❌ **{kit}** kiti için yetkiniz yok! / No permission for this kit!", ephemeral=True)

    await interaction.response.defer()

    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT tier, discord_id FROM oyuncular WHERE minecraft_nick COLLATE NOCASE = ? AND kit = ?", (nick, kit))
    kayit = cursor.fetchone()

    if not kayit:
        conn.close()
        return await interaction.followup.send(f"❌ `{nick}` adlı oyuncunun **{kit}** kitinde bir tier kaydı bulunamadı!", ephemeral=True)

    eski_tier = kayit[0]
    discord_id = kayit[1]

    kullanici = interaction.guild.get_member(discord_id)
    if kullanii:
        rol_adi = f"{kit} {eski_tier}".lower()
        for role in kullanici.roles:
            if role.name.lower() == rol_adi:
                try: 
                    await kullanici.remove_roles(role)
                except: 
                    pass

    cursor.execute("DELETE FROM oyuncular WHERE minecraft_nick COLLATE NOCASE = ? AND kit = ?", (nick, kit))
    conn.commit()

    embed = discord.Embed(
        title="🗑️ Star Tier List | Tier Silindi", 
        description=f"**{nick}** adlı oyuncunun **{kit}** tier'i {interaction.user.mention} tarafından silindi.", 
        color=discord.Color.orange()
    )
    
    await interaction.followup.send(embed=embed)

    cursor.execute("SELECT deger FROM ayarlar WHERE ayar_adi = 'tier_kanali'")
    kanal_ayari = cursor.fetchone()
    
    if kanal_ayari:
        log_kanali = interaction.guild.get_channel(int(kanal_ayari[0]))
        if log_kanali: 
            await log_kanali.send(embed=embed)
        
    conn.close()


@bot.tree.command(name="hile", description="TR: Oyuncuyu banlar ve Blacklist'e atar.")
@app_commands.describe(kullanici="Discord Hesabı", nick="Minecraft Nicki", sebep="Sebep", sure_ay="Kaç Ay", kanit="Kanıt Fotoğrafı")
async def hile(interaction: discord.Interaction, kullanici: discord.Member, nick: str, sebep: str, sure_ay: int, kanit: discord.Attachment = None):
    await hile_islem_merkezi(interaction, kullanici, nick, sebep, sure_ay, kanit)

@bot.tree.command(name="ban", description="EN: Bans a player and adds them to the Blacklist.")
@app_commands.describe(kullanici="Discord Account", nick="Minecraft Nick", sebep="Reason", sure_ay="Duration (Months)", kanit="Proof Image")
async def ban(interaction: discord.Interaction, kullanici: discord.Member, nick: str, sebep: str, sure_ay: int, kanit: discord.Attachment = None):
    await hile_islem_merkezi(interaction, kullanici, nick, sebep, sure_ay, kanit)

@bot.tree.command(name="sonuc", description="TR: Bir oyuncuya Tier verir ve sonucu yazar.")
@app_commands.choices(
    kit=[app_commands.Choice(name=k, value=k) for k in KITLER], 
    tier=[app_commands.Choice(name=t, value=t) for t in TIERLAR]
)
async def sonuc(interaction: discord.Interaction, nick: str, discord_kullanici: discord.Member, kit: app_commands.Choice[str], tier: app_commands.Choice[str], skor: str, sunucu: str):
    await sonuc_islem_merkezi(interaction, nick, discord_kullanici, kit.value, tier.value, skor, sunucu)

@bot.tree.command(name="result", description="EN: Evaluates a player and logs the result.")
@app_commands.choices(
    kit=[app_commands.Choice(name=k, value=k) for k in KITLER], 
    tier=[app_commands.Choice(name=t, value=t) for t in TIERLAR]
)
async def result(interaction: discord.Interaction, nick: str, discord_kullanici: discord.Member, kit: app_commands.Choice[str], tier: app_commands.Choice[str], skor: str, sunucu: str):
    await sonuc_islem_merkezi(interaction, nick, discord_kullanici, kit.value, tier.value, skor, sunucu)

@bot.tree.command(name="profil", description="TR: Tier profilini gösterir.")
async def profil(interaction: discord.Interaction, kullanici: discord.Member = None):
    hedef = kullanici or interaction.user
    await interaction.response.defer()
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT minecraft_nick, uuid, kit, tier, skor, region FROM oyuncular WHERE discord_id = ?", (hedef.id,))
    kayitlar = cursor.fetchall()
    conn.close()
    
    if not kayitlar: 
        return await interaction.followup.send(f"❌ {hedef.mention} henüz hiçbir testte bulunmamış!", ephemeral=True)
        
    mc_nick, kayit_uuid = kayitlar[-1][0], kayitlar[-1][1]
    is_premium = kayit_uuid != "non-premium"
    gorsel_uuid = kayit_uuid if is_premium else STEVE_UUID
    gorunen_nick = mc_nick if is_premium else f"{mc_nick} (Non Premium)"
    
    embed = discord.Embed(
        title=f"Star Tier List | {gorunen_nick}", 
        description=f"{hedef.mention} test sonuçları.", 
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=f"https://visage.surgeplay.com/bust/512/{gorsel_uuid}")
    embed.set_author(name=hedef.display_name, icon_url=hedef.display_avatar.url)
    
    for kayit in kayitlar:
        kit_adi = kayit[2]
        kit_emoji = get_kit_emoji(kit_adi) 
        embed.add_field(
            name=f"{kit_emoji} {kit_adi}", 
            value=f"**Tier:** {uzun_tier_ismi(kayit[3])}\n**Score:** {kayit[4]}\n**Region:** {kayit[5].upper()}", 
            inline=True
        )
        
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="profile", description="EN: Shows Tier profile.")
async def profile(interaction: discord.Interaction, kullanici: discord.Member = None):
    hedef = kullanici or interaction.user
    await interaction.response.defer()
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT minecraft_nick, uuid, kit, tier, skor, region FROM oyuncular WHERE discord_id = ?", (hedef.id,))
    kayitlar = cursor.fetchall()
    conn.close()
    
    if not kayitlar: 
        return await interaction.followup.send(f"❌ {hedef.mention} has no evaluation records found.", ephemeral=True)
        
    mc_nick, kayit_uuid = kayitlar[-1][0], kayitlar[-1][1]
    is_premium = kayit_uuid != "non-premium"
    gorsel_uuid = kayit_uuid if is_premium else STEVE_UUID
    gorunen_nick = mc_nick if is_premium else f"{mc_nick} (Non Premium)"
    
    embed = discord.Embed(
        title=f"Star Tier List | {gorunen_nick}", 
        description=f"{hedef.mention}'s evaluation results.", 
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=f"https://visage.surgeplay.com/bust/512/{gorsel_uuid}")
    embed.set_author(name=hedef.display_name, icon_url=hedef.display_avatar.url)
    
    for kayit in kayitlar:
        kit_adi = kayit[2]
        kit_emoji = get_kit_emoji(kit_adi) 
        embed.add_field(
            name=f"{kit_emoji} {kit_adi}", 
            value=f"**Tier:** {uzun_tier_ismi(kayit[3])}\n**Score:** {kayit[4]}\n**Region:** {kayit[5].upper()}", 
            inline=True
        )
        
    await interaction.followup.send(embed=embed)


# ================= KLAN AUTOCOMPLETE VE AÇIK KLAN KOMUTLARI =================
async def klan_autocomplete(interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT klan_adi FROM klan_bilgi")
    klanlar = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    return [
        app_commands.Choice(name=k, value=k)
        for k in klanlar if current.lower() in k.lower()
    ][:25] 

@bot.tree.command(name="klan_profil", description="TR: Kayıtlı bir klanın profilini ve üyelerini gösterir.")
@app_commands.describe(klan_ismi="Profilini görmek istediğiniz klan")
@app_commands.autocomplete(klan_ismi=klan_autocomplete)
async def klan_profil(interaction: discord.Interaction, klan_ismi: str):
    await interaction.response.defer()
    klan_adi = klan_ismi.upper()

    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT kurucu_nick, kurucu_discord FROM klan_bilgi WHERE klan_adi = ?", (klan_adi,))
    klan_data = cursor.fetchone()

    if not klan_data:
        conn.close()
        return await interaction.followup.send(f"❌ `{klan_adi}` adında kayıtlı bir klan bulunamadı.")

    kurucu_nick, kurucu_discord_id = klan_data
    cursor.execute("SELECT DISTINCT minecraft_nick FROM oyuncular WHERE klan = ?", (klan_adi,))
    uyeler = cursor.fetchall()
    conn.close()

    uye_sayisi = len(uyeler)
    uye_listesi = "\n".join([f"• {u[0]}" for u in uyeler[:15]])
    if uye_sayisi > 15:
        uye_listesi += f"\n...ve {uye_sayisi - 15} kişi daha."
    if not uye_listesi:
        uye_listesi = "Henüz üye yok."

    embed = discord.Embed(title=f"👑 {klan_adi} Klan Profili", color=discord.Color.purple())
    kurucu_mention = f"<@{kurucu_discord_id}>" if kurucu_discord_id else "Bilinmiyor"
    
    embed.add_field(name="Kurucu (Minecraft)", value=f"`{kurucu_nick}`", inline=True)
    embed.add_field(name="Kurucu (Discord)", value=kurucu_mention, inline=True)
    embed.add_field(name="Üye Sayısı", value=str(uye_sayisi), inline=True)
    embed.add_field(name="👥 Klan Üyeleri", value=f"```\n{uye_listesi}\n```", inline=False)

    logo_path = f"web/static/klanlar/{klan_adi}_logo.png"
    bg_path = f"web/static/klanlar/{klan_adi}_bg.png"

    files = []
    if os.path.exists(logo_path):
        file_logo = discord.File(logo_path, filename="logo.png")
        embed.set_thumbnail(url="attachment://logo.png")
        files.append(file_logo)
        
    if os.path.exists(bg_path):
        file_bg = discord.File(bg_path, filename="bg.png")
        embed.set_image(url="attachment://bg.png")
        files.append(file_bg)

    await interaction.followup.send(embed=embed, files=files)

@bot.tree.command(name="clan_profile", description="EN: Shows the profile and members of a registered clan.")
@app_commands.describe(klan_ismi="The clan you want to view")
@app_commands.autocomplete(klan_ismi=klan_autocomplete)
async def clan_profile(interaction: discord.Interaction, klan_ismi: str):
    await interaction.response.defer()
    klan_adi = klan_ismi.upper()

    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("SELECT kurucu_nick, kurucu_discord FROM klan_bilgi WHERE klan_adi = ?", (klan_adi,))
    klan_data = cursor.fetchone()

    if not klan_data:
        conn.close()
        return await interaction.followup.send(f"❌ No registered clan found with the name `{klan_adi}`.")

    kurucu_nick, kurucu_discord_id = klan_data
    cursor.execute("SELECT DISTINCT minecraft_nick FROM oyuncular WHERE klan = ?", (klan_adi,))
    uyeler = cursor.fetchall()
    conn.close()

    uye_sayisi = len(uyeler)
    uye_listesi = "\n".join([f"• {u[0]}" for u in uyeler[:15]])
    if uye_sayisi > 15:
        uye_listesi += f"\n...and {uye_sayisi - 15} more members."
    if not uye_listesi:
        uye_listesi = "No members yet."

    embed = discord.Embed(title=f"👑 {klan_adi} Clan Profile", color=discord.Color.purple())
    kurucu_mention = f"<@{kurucu_discord_id}>" if kurucu_discord_id else "Unknown"
    
    embed.add_field(name="Founder (Minecraft)", value=f"`{kurucu_nick}`", inline=True)
    embed.add_field(name="Founder (Discord)", value=kurucu_mention, inline=True)
    embed.add_field(name="Member Count", value=str(uye_sayisi), inline=True)
    embed.add_field(name="👥 Clan Members", value=f"```\n{uye_listesi}\n```", inline=False)

    logo_path = f"web/static/klanlar/{klan_adi}_logo.png"
    bg_path = f"web/static/klanlar/{klan_adi}_bg.png"

    files = []
    if os.path.exists(logo_path):
        file_logo = discord.File(logo_path, filename="logo.png")
        embed.set_thumbnail(url="attachment://logo.png")
        files.append(file_logo)
        
    if os.path.exists(bg_path):
        file_bg = discord.File(bg_path, filename="bg.png")
        embed.set_image(url="attachment://bg.png")
        files.append(file_bg)

    await interaction.followup.send(embed=embed, files=files)


# ================= GİZLİ KLAN KOMUTLARI (SADECE İKİ PATRON) =================

@bot.tree.command(name="klan_olustur", description="TR: Yeni bir klan oluşturur. (Sadece Yönetici)")
@app_commands.describe(isim="Klan İsmi", kurucu="Kurucu Nick", kurucu_discord="Kurucu Discord", logo="Logo (PNG/JPG)", arkaplan="Arka Plan (PNG/JPG)")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def klan_olustur(interaction: discord.Interaction, isim: str, kurucu: str, kurucu_discord: discord.Member, logo: discord.Attachment, arkaplan: discord.Attachment):
    await interaction.response.defer(ephemeral=True)
    klan_adi = isim.upper()
    
    logo_path = f"web/static/klanlar/{klan_adi}_logo.png"
    bg_path = f"web/static/klanlar/{klan_adi}_bg.png"
    
    try:
        await logo.save(logo_path)
        await arkaplan.save(bg_path)
    except Exception as e:
        return await interaction.followup.send(f"❌ Fotoğraf kaydetme hatası: {e}")
    
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("REPLACE INTO klan_bilgi (klan_adi, kurucu_nick, kurucu_discord) VALUES (?, ?, ?)", (klan_adi, kurucu, str(kurucu_discord.id)))
    conn.commit()
    conn.close()
    
    await interaction.followup.send(f"👑 **{klan_adi}** klanı başarıyla oluşturuldu! Logo ve arka plan site klasörüne kaydedildi.")

@bot.tree.command(name="klan_ekle", description="TR: Oyuncuyu klana ekler. (Sadece Yönetici)")
@app_commands.describe(nick="Minecraft Nicki", klan_ismi="Katılacağı Klanın Adı")
@app_commands.autocomplete(klan_ismi=klan_autocomplete)
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def klan_ekle(interaction: discord.Interaction, nick: str, klan_ismi: str):
    await interaction.response.defer(ephemeral=True)
    klan_adi = klan_ismi.upper()
    
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE oyuncular SET klan = ? WHERE minecraft_nick COLLATE NOCASE = ?", (klan_adi, nick))
    
    if cursor.rowcount == 0:
        await interaction.followup.send(f"❌ `{nick}` adına tier kaydı bulunamadı. Önce adamın tier alması lazım.")
    else:
        await interaction.followup.send(f"✅ **{nick}** adlı oyuncu **{klan_adi}** klanına başarıyla eklendi!")
        
    conn.commit()
    conn.close()

@bot.tree.command(name="klan_cikar", description="TR: Oyuncuyu klandan atar. (Sadece Yönetici)")
@app_commands.describe(nick="Klandan atılacak oyuncunun nicki")
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def klan_cikar(interaction: discord.Interaction, nick: str):
    await interaction.response.defer(ephemeral=True)
    
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE oyuncular SET klan = NULL WHERE minecraft_nick COLLATE NOCASE = ?", (nick,))
    conn.commit()
    conn.close()
    
    await interaction.followup.send(f"🗑️ **{nick}** başarıyla klandan atıldı.")

@bot.tree.command(name="klan_sil", description="TR: Bir klanı komple yok eder. (Sadece Yönetici)")
@app_commands.describe(klan_ismi="Silinecek Klanın Adı")
@app_commands.autocomplete(klan_ismi=klan_autocomplete)
@app_commands.default_permissions(administrator=True)
@sadece_sahip()
async def klan_sil(interaction: discord.Interaction, klan_ismi: str):
    await interaction.response.defer(ephemeral=True)
    klan_adi = klan_ismi.upper()
    
    conn = sqlite3.connect("tierlist.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM klan_bilgi WHERE klan_adi = ?", (klan_adi,))
    cursor.execute("UPDATE oyuncular SET klan = NULL WHERE klan = ?", (klan_adi,))
    conn.commit()
    conn.close()
    
    await interaction.followup.send(f"💣 **{klan_adi}** klanı ve tüm üye verileri başarıyla yok edildi!")

@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name="www.startierlist.com"))
    print(f"Star Tier List | {bot.user} HİÇBİR EKSİK OLMADAN, GENİŞLETİLMİŞ TAM SÜRÜMLE AKTİF!")

# DİKKAT: TOKEN BURAYA!
bot.run("MY_TOCKEN")
