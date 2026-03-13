import sqlite3
import requests
import time
import datetime

# Veritabanı yolu app.py ile aynı olmalı
DB_PATH = "../tierlist.db" 

def mojang_isim_sorgula(uuid):
    """Mojang API'sine bağlanıp UUID'nin güncel ismini çeker."""
    try:
        url = f"https://sessionserver.mojang.com/session/minecraft/profile/{uuid}"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("name")
    except Exception as e:
        print(f"Hata: {uuid} sorgulanamadı. Detay: {e}", flush=True)
    return None

def isimleri_guncelle_dongusu():
    print("🚀 Mojang Senkronizasyon Botu Başlatıldı! (Sonsuz Döngü Modu)", flush=True)
    tur_sayisi = 1

    while True:
        zaman = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n--- [TUR {tur_sayisi}] Başlıyor | Zaman: {zaman} ---", flush=True)
        
        # Her turda veritabanına yeniden bağlanıyoruz ki güncel oyuncu listesini alsın
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT DISTINCT uuid, minecraft_nick FROM oyuncular WHERE uuid IS NOT NULL AND uuid != 'non-premium'")
        oyuncular = cursor.fetchall()

        print(f"Toplam {len(oyuncular)} premium oyuncu sirayla kontrol ediliyor...", flush=True)

        guncellenen_sayisi = 0

        for uuid, eski_isim in oyuncular:
            # Mojang'dan ban yememek için tam 30 saniye bekle
            time.sleep(30) 
            
            yeni_isim = mojang_isim_sorgula(uuid)
            
            if yeni_isim and yeni_isim != eski_isim:
                print(f"✅ [İSİM DEĞİŞTİ] Eski: {eski_isim} --> Yeni: {yeni_isim}", flush=True)
                
                cursor.execute("UPDATE oyuncular SET minecraft_nick = ? WHERE uuid = ?", (yeni_isim, uuid))
                cursor.execute("UPDATE hile_listesi SET minecraft_nick = ? WHERE uuid = ?", (yeni_isim, uuid))
                cursor.execute("UPDATE klan_bilgi SET kurucu_nick = ? WHERE kurucu_nick COLLATE NOCASE = ?", (yeni_isim, eski_isim))
                
                guncellenen_sayisi += 1
                conn.commit()

        conn.close()
        
        bitis_zamani = datetime.datetime.now().strftime("%H:%M:%S")
        print(f"--- [TUR {tur_sayisi}] Tamamlandı | {guncellenen_sayisi} kişi güncellendi | Saat: {bitis_zamani} ---", flush=True)
        print("Hemen yeni tura geçiliyor...", flush=True)
        
        tur_sayisi += 1

if __name__ == "__main__":
    isimleri_guncelle_dongusu()