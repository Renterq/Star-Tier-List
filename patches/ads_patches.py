import sqlite3
import os

DB_PATH = "tierlist.db"

def reklam_kurtar():
    if not os.path.exists(DB_PATH):
        print("tierlist.db bulunamadı!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Bozuk dökümandan süzdüğüm o reklam verileri
    reklamlar = [
        (
            'KINGDOM OF VLANDIA', 
            'Kingdom of Vlandia - Aktif ekip alımları, Disiplinli ve sağlam ekip yapısı, Para Yardımı, Her şey Yapılandırma, Düzenli çekilişler ve etkinlikler. Burada sadece oynamak değil; birlikte güçlenmek, birlikte yükselmek.', 
            'https://discord.gg/vlandiamc', 
            '/static/reklamlar/KINGDOM_OF_VLANDIA.png'
        ),
        (
            'Hititler', 
            'H İ T İ T L E R - Oldukça aktif bir ekibiz. PVP gelişiminde yardımcı oluyoruz. Kurallar herkese eşittir. Şartlar: En az bir kitte HT5+ olmak, seslerde aktiflik ve bioya Hititler uzantısı eklemek. WE NEVER LOSE.', 
            'https://discord.gg/2HxK67rARD', 
            '/static/reklamlar/Hititler.gif'
        ),
        (
            'Reklam Ver', 
            'Reklam Vermek isteyenler Discord sunucumuzda ticket açarak iletişime geçebilir.', 
            'https://discord.gg/startier', 
            '/static/reklamlar/Reklam_Vermek_istiyenler.jpg'
        )
    ]

    for r in reklamlar:
        cursor.execute("SELECT isim FROM reklam_discordlar WHERE isim=?", (r[0],))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO reklam_discordlar (isim, aciklama, url, gorsel_url) VALUES (?, ?, ?, ?)", r)
            print(f"Reklam Geri Geldi: {r[0]}")

    conn.commit()
    conn.close()
    print("-" * 30)
    print("REKLAM YAMASI TAMAM! Site ana sayfası artık eskisi gibi dopdolu.")

if __name__ == "__main__":
    reklam_kurtar()
