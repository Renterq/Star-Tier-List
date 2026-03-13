import sqlite3
import re
import os

DB_PATH = "tierlist.db"
# Dosyayı az önce taşıdığımız için yeni yolunu belirtiyoruz
TXT_PATH = "bozuk_veriler/kurtarilan_yazilar.txt" if os.path.exists("bozuk_veriler/kurtarilan_yazilar.txt") else "kurtarilan_yazilar.txt"

def klan_kurtar():
    if not os.path.exists(DB_PATH):
        print("tierlist.db bulunamadı!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. Klanları tabloya geri ekle (Renkleri ve Kurucuları ile)
    klanlar = [
        ('KRYOS', 'BuSonMu', '1254208513333268515', 'https://discord.gg/ekqX7uAWWx', '#ef4444'),
        ('GNG', 'ZeyIsHere', '1104335274865070161', 'https://discord.gg/gngmc', '#a855f7'),
        ('FAREGANG', 't2llah', '764029369085591582', '', '#f97316'),
        ('1071', 'YALIN0123', '772711742606147605', '', '#a855f7')
    ]
    
    for klan in klanlar:
        cursor.execute("SELECT klan_adi FROM klan_bilgi WHERE klan_adi=?", (klan[0],))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO klan_bilgi (klan_adi, kurucu_nick, kurucu_discord, discord_url, renk) VALUES (?, ?, ?, ?, ?)", klan)
            print(f"Klan Geri Getirildi: {klan[0]}")

    # 2. Dosyayı okuyup oyuncuları kendi klanlarına bağla
    if os.path.exists(TXT_PATH):
        with open(TXT_PATH, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()

        guncellenen = 0
        for i in range(len(lines)):
            line = lines[i].strip()
            # Oyuncuyu bul
            match_nick = re.search(r'3([a-zA-Z0-9_]{2,16})(non-premium|[a-fA-F0-9]{32})', line)
            if match_nick:
                nick = match_nick.group(1)
                
                # Altındaki 5 satırda klan adını ara
                for j in range(1, 6):
                    if i + j < len(lines):
                        lookahead = lines[i+j]
                        match_klan = re.search(r'(FAREGANG|GNG|KRYOS|1071)', lookahead)
                        if match_klan:
                            klan_adi = match_klan.group(1)
                            # Oyuncunun klanını güncelle
                            cursor.execute("UPDATE oyuncular SET klan=? WHERE minecraft_nick=? AND (klan='' OR klan IS NULL)", (klan_adi, nick))
                            if cursor.rowcount > 0:
                                guncellenen += cursor.rowcount
                                print(f"Oyuncu Klana Bağlandı: {nick} -> {klan_adi}")
                            break

    conn.commit()
    conn.close()
    print("-" * 30)
    print("KLAN YAMASI BİTTİ! Klanlar siteye eklendi ve oyuncular klanlarına bağlandı.")

if __name__ == "__main__":
    klan_kurtar()
