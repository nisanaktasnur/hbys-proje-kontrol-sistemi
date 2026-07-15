# LinkedIn Paylaşım Taslağı (Türkçe)

Son dönemde **HBYS Proje Kontrol ve Karar Destek Sistemi** adlı bir demo/portföy projesi geliştirdim.

HBYS uygulama projelerinde talep takibi, risk yönetimi, UAT süreçleri, canlı geçiş hazırlığı ve ekip içi koordinasyon genellikle farklı araçlar ve e-posta zincirleri üzerinden yürütülür. Bu proje, bu süreçleri tek bir **rol tabanlı Django platformu** altında toplamayı amaçlayan bir prototiptir.

**Problem:** HBYS projelerinde operasyonel talepler, teknik işler, riskler ve yönetici özeti aynı anda izlenmeli; ancak her rol farklı sorumluluklara sahiptir.

**Çözüm:** Django ile geliştirilmiş, dört rol için ayrı paneller sunan bir karar destek uygulaması:

- Sistem Yöneticisi — kurum, proje ve kullanıcı yönetimi
- Proje Yöneticisi — talep, risk, UAT ve karar destek
- Teknik Lider — teknik iş listesi, teknik riskler ve UAT bulguları
- Yönetici — stratejik salt okunur özet

**Öne çıkan özellikler:**
- Kurum / proje bağlamı seçimi
- 3×3 risk matrisi ve detay listesi
- Proje iletişim ve talimat merkezi
- CSV dışa aktarma
- Demo veri tohumlama ve otomatik QA betikleri

**Teknolojiler:** Django, Python, SQLite (PostgreSQL yapısına hazır), HTML/CSS, rol tabanlı izinler, CSV raporlama, pytest

Bu proje bir **portföy / demo** çalışmasıdır; gerçek hasta veya hastane verisi içermez ve üretim ortamı için ek güvenlik sertleştirmesi gerektirir.

Geri bildirimlere açığım.

#Django #Python #HealthTech #ProjectManagement #BusinessAnalysis #SoftwareDevelopment
