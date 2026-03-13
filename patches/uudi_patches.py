import sqlite3
import re
import os

DB_PATH = "tierlist.db"
TXT_PATH = "kurtarilan_yazilar.txt"

def uuid_kurtar():
    if not os.path.exists(DB_PATH):
        print("tierlist.db bulunamadı!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(TXT_PATH, "r", encoding="utf-8", errors="ignore") as f:
        icerik = f.read()

    # Nick ve 32 haneli UUID'yi yan yana yakalayan kural
    # Örnek: 3RENTER__4586269f710049e6b203d4b5f993d61d
    pattern = r'3([a-zA-Z0-9_]{2,16})(non-premium|[a-fA-F0-9]{32})'
    bulunanlar = re.findall(pattern, icerik)

    guncellenen = 0
    for match in bulunanlar:
        nick = match[0]
        gercek_uuid = match[1]

        # Eğer gerçek UUID 'non-premium'dan farklıysa (yani premiumsa), veritabanında o oyuncuyu bul ve düzelt
        if gercek_uuid != "non-premium":
            cursor.execute("UPDATE oyuncular SET uuid = ? WHERE minecraft_nick = ? AND uuid = 'non-premium'", (gercek_uuid, nick))
            if cursor.rowcount > 0:
                guncellenen += cursor.rowcount
                print(f"Skin/UUID Geri Geldi: {nick} -> {gercek_uuid}")

    conn.commit()
    conn.close()

    print("-" * 30)
    print(f"PREMİUM YAMASI BİTTİ! Toplam {guncellenen} oyuncunun skini başarıyla kurtarıldı.")

if __name__ == "__main__":
    uuid_kurtar()
