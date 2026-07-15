# HBYS Proje Kontrol ve Karar Destek Sistemi

**Kısa arayüz adı:** HBYS Proje Kontrol Sistemi

Django tabanlı, rol odaklı bir hastane bilgi yönetim sistemi (HBYS) uygulama proje kontrol ve karar destek platformudur. HBYS uygulama projelerinde talep takibi, risk yönetimi, UAT bulguları, canlı geçiş hazırlığı, teknik aksiyonlar ve yönetici özetlerini tek bir yapı altında yönetmek için geliştirilmiştir.

> **Önemli:** Bu proje bir **portföy / demo** uygulamasıdır. Gerçek hasta, hastane veya kurum verisi içermez. Tıbbi karar verme sistemi değildir; HBYS uygulama süreçleri için proje yönetimi ve karar desteği amaçlı bir prototiptir.

---

## Özellikler

- Rol tabanlı erişim kontrolü (Sistem Yöneticisi, Proje Yöneticisi, Teknik Lider, Yönetici)
- Kurum / hastane ve proje bağlamı seçimi
- Sistem Yöneticisi kurum, proje ve kullanıcı yönetimi
- Proje Yöneticisi talep, risk, UAT ve karar destek yönetimi
- Teknik Lider teknik operasyon paneli, iş listesi, teknik riskler, UAT teknik bulguları ve teknik aksiyonlar
- Yönetici stratejik salt okunur panel
- Proje iletişim ve talimat merkezi (mesaj / talimat akışı)
- 3×3 risk matrisi ve matrise göre risk detay listesi
- Koşullu talep formu doğrulaması
- CSV dışa aktarma (Türkçe başlıklar, rol bazlı yetki)
- Yapay zekâ proje asistanı
- Demo veri tohumlama (`seed_demo_data`)
- Tam sistem QA ve doğrulama betikleri

---

## Roller

| Rol | Açılış sayfası | Sorumluluk |
|-----|----------------|------------|
| **Sistem Yöneticisi** | Kullanıcı Yönetimi | Kullanıcı onayı, kurum/proje yönetimi, sistem kayıtları, genel görünüm |
| **Proje Yöneticisi** | Genel Görünüm | Talep, risk, UAT, karar destek, iletişim merkezi, yapay zekâ asistanı |
| **Teknik Lider** | Teknik Operasyon Özeti | Teknik iş listesi, teknik riskler, UAT teknik bulguları, teknik aksiyonlar |
| **Yönetici** | Yönetici Paneli | Stratejik salt okunur özet, yönetici özeti, iletişim merkezi |

---

## Demo hesaplar

Giriş sayfasında demo hesaplar görüntülenir. Yerel kurulumda aşağıdaki hesaplar `seed_demo_data` ile oluşturulur:

| Kullanıcı | Şifre | Rol |
|-----------|-------|-----|
| `admin` | `Admin123!` | Sistem Yöneticisi |
| `pm` | `Pm123!` | Proje Yöneticisi |
| `techlead` | `Tech123!` | Teknik Lider |
| `manager` | `Manager123!` | Yönetici |

> Bu hesaplar yalnızca demo amaçlıdır. Üretim ortamında kullanılmamalıdır.

**Giriş adresi:** http://127.0.0.1:8000/giris/

---

## Kurulum (Windows PowerShell)

```powershell
cd hbys_proje_kontrol_sistemi
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
$env:DJANGO_SETTINGS_MODULE = "config.settings_local"
python manage.py migrate
python manage.py seed_demo_data
python manage.py runserver
```

Tarayıcıda http://127.0.0.1:8000/giris/ adresine gidin.

### Docker (isteğe bağlı)

```powershell
copy .env.example .env
docker compose up --build
```

---

## Demo veri

```powershell
python manage.py seed_demo_data
```

Komut şunları oluşturur:

- **Demo hastaneler:** Örnek Şehir Hastanesi, Örnek Eğitim ve Araştırma Hastanesi, Örnek Diş Hastanesi
- Her hastane altında birden fazla proje
- Demo kullanıcılar ve `ProjectMembership` kayıtları
- Talepler, proje riskleri, teknik riskler, UAT kayıtları
- Karar destek kayıtları, canlı geçiş metrikleri
- Demo mesaj ve talimat kayıtları

---

## Test ve doğrulama

```powershell
$env:DJANGO_SETTINGS_MODULE = "config.settings_local"
python -m pytest -q
python scripts/run_verification.py
python scripts/verify_role_experience.py
python scripts/full_system_qa.py
```

### Güncel doğrulanmış durum

| Kontrol | Sonuç |
|---------|-------|
| `pytest` | **73 passed** |
| `run_verification.py` | **27/27 geçti** |
| `verify_role_experience.py` | **8/8 geçti** |
| `full_system_qa.py` | **169/169 geçti** |

Detaylı QA raporu: [`QA_REPORT.md`](QA_REPORT.md)

---

## Proje yapısı

```
hbys_proje_kontrol_sistemi/
├── accounts/        # Kimlik doğrulama, kullanıcı yönetimi, üyelik
├── assistant/       # Yapay zekâ proje asistanı
├── config/          # Django ayarları (local, test, production)
├── core/            # Kurum/proje bağlamı, izinler, demo seed komutu
├── projects/        # Talep, risk, UAT, karar, iletişim modülleri
├── reports/         # CSV dışa aktarma
├── scripts/         # Doğrulama ve tam sistem QA betikleri
├── templates/       # Türkçe arayüz şablonları
└── static/          # CSS ve statik dosyalar
```

---

## Ana ekranlar / modüller

- Sistem Yöneticisi Genel Görünüm
- Kullanıcı Yönetimi
- Kurum ve Proje Yönetimi
- Sistem Kayıtları
- Proje Yöneticisi Genel Görünüm
- Talep Yönetimi
- Risk Erken Uyarı
- Karar Destek Merkezi
- Yapay Zekâ Proje Asistanı
- Teknik Operasyon Özeti
- Teknik İş Listesi
- Teknik Riskler
- UAT Teknik Bulguları
- Teknik Aksiyonlar
- Yönetici Paneli
- Yönetici Özeti
- Proje İletişim ve Talimat Merkezi

---

## Sınırlılıklar

- Bu sürüm **demo / portföy** amaçlıdır; üretim kullanımı için güvenlik sertleştirmesi gerekir.
- PostgreSQL / Docker üretim doğrulaması gerçek kullanımdan önce tamamlanmalıdır.
- Gerçek hastane sistemleriyle entegrasyon bulunmaz.
- Yapay zekâ asistanı harici API anahtarı olmadan deterministik / demo mantığı ile çalışır.
- Arayüz tamamen Türkçedir; gerçek kurum, marka veya hasta verisi kullanılmaz.

---

## GitHub notu

Bu depoda **gerçek hasta, hastane veya kurum verisi bulunmaz**. Tüm örnek veriler `seed_demo_data` komutu ile oluşturulan temsili demo kayıtlarıdır. `.env`, veritabanı dosyaları (`*.sqlite3`), sanal ortam ve önbellek dosyaları depoya dahil edilmemelidir.

---

## Lisans

MIT
