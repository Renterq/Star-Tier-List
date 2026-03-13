import sqlite3
import re
import os

DB_PATH = "tierlist.db"
TXT_PATH = "kurtarilan_yazilar.txt"

KITLER = ["Nethpot", "Sword", "Axe", "SMP", "DiaSMP", "Mace", "Pot", "UHC", "Vanilla", "Crystal"]
TIERLAR = ["HT1", "HT2", "HT3", "HT4", "HT5", "LT1", "LT2", "LT3", "LT4", "LT5"]

def kurtar_ve_yaz():
    if not os.path.exists(DB_PATH):
        print("tierlist.db bulunamadı! Önce siteyi çalıştırıp boş db oluşmasını sağla.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    with open(TXT_PATH, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    eklenen_oyuncu = 0
    
    for i in range(len(lines)):
        line = lines[i].strip()
        
        # Oyuncu ismini bul (Örn: 3RENTER__458626... veya 3xNyksnon-premium)
        match_nick = re.search(r'3([a-zA-Z0-9_]{2,16})(non-premium|[a-fA-F0-9]{32})', line)
        if match_nick:
            nick = match_nick.group(1)
            
            # İsmi bulduk, altındaki 5 satırı tara ve Kit+Tier kombinasyonunu yakala
            for j in range(1, 6):
                if i + j < len(lines):
                    lookahead_line = lines[i+j]
                    match_kit_tier = re.search(r'(' + '|'.join(KITLER) + r')(' + '|'.join(TIERLAR) + r')', lookahead_line, re.IGNORECASE)
                    
                    if match_kit_tier:
                        kit = match_kit_tier.group(1).capitalize()
                        tier = match_kit_tier.group(2).upper()
                        
                        # Eğer bu nick ve kit daha önce eklenmediyse veritabanına yaz
                        cursor.execute("SELECT id FROM oyuncular WHERE minecraft_nick=? AND kit=?", (nick, kit))
                        if not cursor.fetchone():
                            cursor.execute("""
                                INSERT INTO oyuncular (minecraft_nick, uuid, discord_id, kit, tier, region, tester_id, skor, klan) 
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (nick, "non-premium", 0, kit, tier, "Kurtarildi", 0, "-", ""))
                            eklenen_oyuncu += 1
                            print(f"Başarılı -> {nick} | {kit} {tier}")
                        break # Bu oyuncunun kitini bulduk, alt satırları taramayı bırak

    conn.commit()
    conn.close()
    
    print("-" * 30)
    print(f"ZORLU KURTARMA BİTTİ! Toplam {eklenen_oyuncu} oyuncu verisi geri getirildi.")

if __name__ == "__main__":
    kurtar_ve_yaz()
