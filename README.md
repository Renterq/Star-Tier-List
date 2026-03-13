# Star-Tier-List
# ⭐ Star Tier List & Ranking System
*(English description is available below)*

Bu proje, Minecraft PvP sunucuları için tasarlanmış kapsamlı bir oyuncu sıralama (Tier), eşleştirme ve yönetim sistemidir. İki ana bileşenden oluşur: Yönetim için kullanılan bir **Discord Botu (v3.2)** ve oyuncu sıralamalarını canlı olarak gösteren, Minecraft oyun içi modlarına veri sağlayan bir **Flask Web Sitesi/API**.

## 🚀 Proje Mimarisi ve Özellikler

### 1. Discord Yönetim Botu (Python / discord.py)
Sunucu yetkililerinin oyuncuları yönettiği, maçları kayıt altına aldığı ve oyuncuların durumlarını takip ettiği kontrol merkezidir.
- **Sıralama (Tier) Sistemi:** Oyuncuları yeteneklerine göre renk kodlu (Gold, Silver, Bronze, Purple, Green vb.) seviyelere ayırır.
- **Klan Yönetimi:** Klan kurma, klan profili oluşturma ve üye ekleme/çıkarma işlemleri.
- **Kuyruk (Queue) ve Eşleştirme:** "Crystal" kiti gibi özel oyun modları için bekleme sırası ve maç ayarlama sistemi.
- **Kara Liste (Blacklist) ve Ban Sistemi:** Kuralları ihlal eden oyuncular için süreli veya süresiz uzaklaştırma altyapısı.

### 2. Flask Web Sitesi ve API (Python / Flask)
Oyuncuların genel sıralamaları (Leaderboard) görebildiği, SEO optimizasyonlu (robots.txt, meta etiketleri vb.) ön yüz (Frontend) ve oyun içi sistemler için arka yüz (Backend).
- **Canlı Liderlik Tablosu:** Discord botu üzerinden girilen verileri anında web sitesine yansıtır.
- **Minecraft Mod Entegrasyonu:** Oyun içi modların oyuncu seviyelerini ve ban durumlarını canlı çekebilmesi için tasarlanmış `/api/mod_data` uç noktası.
- **Dinamik Medya Yönetimi:** Sponsor logoları ve görseller için tarayıcı önbelleklemesini (caching) önleyen dinamik dosya isimlendirme altyapısı.

## 🛠️ Kurulum (Installation)

1. Depoyu bilgisayarınıza klonlayın: `git clone https://github.com/KULLANICI_ADINIZ/star-tier-list-system.git`
2. **Discord Botu:** `bot/` klasörüne girin, bot tokeninizi ekleyip `python3 bot.py` ile başlatın.
3. **Web Sitesi:** `website/` klasörüne girin, gerekli kütüphaneleri (`pip install flask`) kurun ve `python3 app.py` komutuyla sunucuyu ayağa kaldırın.

---
---

# ⭐ Star Tier List & Ranking System (English)

This project is a comprehensive player ranking (Tier), matchmaking, and management system designed for Minecraft PvP servers. It consists of two main components: A **Discord Bot (v3.2)** used for administration, and a **Flask Website/API** that displays live player rankings and provides data to in-game Minecraft mods.

## 🚀 Project Architecture & Features

### 1. Discord Management Bot (Python / discord.py)
The control center where server admins manage players, record matches, and track player statuses.
- **Tier System:** Categorizes players into color-coded skill levels (Gold, Silver, Bronze, Purple, Green, etc.).
- **Clan Management:** Infrastructure for clan creation, profiles, and member management.
- **Queue & Matchmaking:** Waitlist and match setup system for specific game modes like the "Crystal" kit.
- **Blacklist & Ban System:** Timed or permanent ban infrastructure for rule-breakers.

### 2. Flask Website & API (Python / Flask)
An SEO-optimized frontend for players to view the global leaderboard, and a backend for in-game systems.
- **Live Leaderboard:** Instantly reflects data entered via the Discord bot onto the website.
- **Minecraft Mod Integration:** A dedicated `/api/mod_data` endpoint designed for in-game mods to fetch player tiers and ban statuses live.
- **Dynamic Media Management:** Dynamic file naming infrastructure for sponsor logos and images to prevent browser caching issues.

## 🛠️ Installation

1. Clone the repository: `git clone https://github.com/YOUR_USERNAME/star-tier-list-system.git`
2. **Discord Bot:** Navigate to the `bot/` folder, add your bot token, and start it with `python3 bot.py`.
3. **Website:** Navigate to the `website/` folder, install required libraries (`pip install flask`), and run the server with `python3 app.py`.
