# HBYS Proje Kontrol ve Karar Destek Sistemi — Portföy Özeti

## Projenin çözdüğü problem

HBYS (Hastane Bilgi Yönetim Sistemi) uygulama projeleri; talep yönetimi, risk takibi, UAT süreçleri, canlı geçiş hazırlığı ve kurum içi koordinasyon gibi birçok paralel iş akışını aynı anda yürütür. Farklı paydaşların (sistem yöneticisi, proje yöneticisi, teknik lider, üst yönetici) aynı veriye farklı perspektiflerden bakması gerekir.

Bu proje, bu karmaşık süreci **rol tabanlı** bir Django uygulaması ile modelleyen bir **demo / portföy** çözümüdür.

## Neden rol tabanlı tasarım?

- Her rol yalnızca ihtiyaç duyduğu ekranları görür.
- Operasyonel işlemler (talep oluşturma, teknik güncelleme) ile stratejik izleme (yönetici paneli) ayrılır.
- Kurum ve proje bağlamı tüm ekranlarda tutarlı kalır.
- Yetkisiz erişim hem menü hem URL düzeyinde engellenir.

## Roller ve sorumluluklar

| Rol | Odak |
|-----|------|
| Sistem Yöneticisi | Kullanıcı, kurum ve proje yönetimi; sistem kayıtları |
| Proje Yöneticisi | Talep, risk, UAT, karar destek ve iletişim yönetimi |
| Teknik Lider | Teknik iş listesi, teknik riskler, UAT bulguları, aksiyonlar |
| Yönetici | Salt okunur stratejik özet ve raporlama |

## Ana modüller

- Talep yönetimi ve koşullu form doğrulaması
- 3×3 risk matrisi ve detay listesi
- UAT ve karar destek merkezi
- Proje iletişim ve talimat merkezi (mesaj / talimat akışı)
- CSV dışa aktarma
- Yapay zekâ proje asistanı
- Demo veri tohumlama ve tam sistem QA betikleri

## Kullanılan teknolojiler

- **Python / Django** — web uygulaması, ORM, kimlik doğrulama
- **SQLite** (yerel) / **PostgreSQL** (Docker yapısına hazır)
- **HTML / CSS** — kurumsal Türkçe arayüz
- **Rol tabanlı izinler** — merkezi `core/permissions.py`
- **pytest** — otomatik testler
- **CSV raporlama** — Türkçe başlıklar, rol bazlı erişim

## Bu proje neyi gösterir?

- Çok rollü bir iş uygulamasında **backend izin modeli** ve **arayüz ayrımı** tasarımı
- Kurum / proje **bağlam yönetimi** (context switching)
- Form doğrulama, risk matrisi ve iş akışı modelleme
- Demo veri, doğrulama betikleri ve QA otomasyonu ile **sürdürülebilir geliştirme** yaklaşımı
- Portföy / GitHub için güvenli yayın hazırlığı (gizli dosya hariç tutma, README, demo hesaplar)

## Önemli not

Bu proje gerçek hasta, hastane veya kurum verisi içermez. Tıbbi karar sistemi değildir; HBYS uygulama proje yönetimi için geliştirilmiş bir **karar destek prototipi**dir.
