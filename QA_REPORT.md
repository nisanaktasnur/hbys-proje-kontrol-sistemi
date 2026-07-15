# HBYS Proje Kontrol Sistemi — QA Raporu

- **Tarih/Saat:** 15.07.2026
- **Ortam:** Yerel (`config.settings_local`)
- **Test kullanıcıları:** admin, pm, techlead, manager

## Özet

| Metrik | Sonuç |
|--------|-------|
| Tam sistem QA kontrolleri | **169/169 geçti** |
| Kritik hata | **0** |
| Majör hata | **0** |
| Minör hata | **0** |

## Ek test komutları

| Komut | Sonuç |
|-------|-------|
| `python -m pytest -q` | **73 passed** |
| `python scripts/run_verification.py` | **27/27 geçti** |
| `python scripts/verify_role_experience.py` | **8/8 geçti** |
| `python scripts/full_system_qa.py` | **169/169 geçti** |

## Test edilen akışlar

- Demo veri tohumlama ve kullanıcı girişleri
- Rol panelleri ve kurum/proje bağlamı
- Sistem Yöneticisi kurum/proje ve sistem kayıtları
- Proje Yöneticisi talep doğrulama, risk matrisi, karar merkezi
- Teknik Lider teknik iş listesi, teknik riskler, UAT, aksiyonlar
- Yönetici stratejik panel ve hastane seçici
- İletişim merkezi tam mesaj/talimat akışı
- Bağlam izolasyonu ve yetkisiz URL erişimi
- CSV dışa aktarma ve sidebar bağlantı taraması

## Test edilen sayfalar (örnek)

- `/`, `/kullanici-yonetimi/`, `/kurum-proje-yonetimi/`, `/sistem-kayitlari/`
- `/talep-yonetimi/`, `/risk-erken-uyari/`, `/karar-destek-merkezi/`
- `/teknik-gorunum/`, `/teknik-is-listesi/`, `/teknik-riskler/`, `/teknik-uat/`, `/teknik-aksiyonlar/`
- `/yonetici-paneli/`, `/yonetici-ozeti/`, `/proje-iletisim-merkezi/`
- `/yapay-zeka-asistani/`, `/disa-aktar/*` (rol bazlı CSV uçları)

## QA kapsamı (169 kontrol)

- **Bölüm 1–2:** Demo veri ve rol panelleri
- **Bölüm 3:** Sistem Yöneticisi akışları
- **Bölüm 4:** Proje Yöneticisi form doğrulama ve risk matrisi
- **Bölüm 5:** Teknik Lider operasyon ekranları
- **Bölüm 6:** Yönetici stratejik panel
- **Bölüm 7:** İletişim ve talimat merkezi
- **Bölüm 8:** Aktif kurum/proje bağlamı ve izolasyon
- **Bölüm 10:** CSV dışa aktarma
- **Bölüm 11:** Sidebar ve bağlantı taraması

## Kalan sınırlamalar

- Tarayıcı (Playwright/Selenium) seviyesinde UI testi yok; Django test istemcisi kullanıldı.
- Harici servis veya canlı ortam testi yapılmadı.
- Yönetici paneli KPI etiketleri spesifikasyonla birebir aynı olmayabilir (minör).
