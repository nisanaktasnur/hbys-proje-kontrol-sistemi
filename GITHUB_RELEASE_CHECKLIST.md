# GitHub Yayın Kontrol Listesi

Yayınlamadan önce aşağıdaki maddeleri doğrulayın.

## Dokümantasyon

- [x] `README.md` güncel sürüme göre yeniden yazıldı
- [x] `PORTFOLIO_SUMMARY.md` eklendi
- [x] `QA_REPORT.md` son QA sonuçlarını içeriyor (yerel yol ve traceback içermez)
- [x] Eski dahili raporlar kaldırıldı (`ENHANCEMENT_REPORT.md`, `VERIFICATION_*`, `ROLE_REFACTOR_REPORT.md`)
- [x] `LINKEDIN_POST.md` hazır
- [x] `.env.example` güvenli örnek değerler içeriyor

## Demo hazırlığı

- [x] Giriş sayfasında **Demo Hesaplar** kartı görünür
- [x] `python manage.py seed_demo_data` temiz veritabanında çalışır
- [x] Demo hastaneler, projeler, kullanıcılar ve kayıtlar oluşturulur
- [x] PM risk matrisi ve teknik risk detayları dolu görünür
- [x] Yönetici paneli anlamlı (sıfır olmayan) KPI değerleri gösterir

## Test durumu

- [x] `python -m pytest -q` → 73 passed
- [x] `python scripts/run_verification.py` → 27/27
- [x] `python scripts/verify_role_experience.py` → 8/8
- [x] `python scripts/full_system_qa.py` → 169/169

## Güvenlik ve depo temizliği

- [x] `.gitignore` güncellendi (`.env`, `*.sqlite3`, `venv/`, `__pycache__/`, `.pytest_cache/`, `staticfiles/`, `*.zip`)
- [x] `.env` dosyası depoya / ZIP'e dahil edilmez
- [x] `db.sqlite3` ve `test_db.sqlite3` dahil edilmez
- [x] Gerçek hasta / hastane / kurum verisi yok
- [x] Demo şifreler yalnızca demo olarak işaretlendi
- [x] Migrasyon dosyaları dahil

## Manuel GitHub yükleme komutları

```powershell
cd hbys_proje_kontrol_sistemi
git init
git add .
git commit -m "Initial portfolio version: HBYS project control system"
git branch -M main
git remote add origin <MY_GITHUB_REPO_URL>
git push -u origin main
```

> `git add .` öncesinde `git status` ile `.env` ve `*.sqlite3` dosyalarının izlenmediğini doğrulayın.

## ZIP paketi

- [x] `hbys_proje_kontrol_sistemi_github_ready.zip` oluşturuldu
- Hariç tutulanlar: `.env`, `*.sqlite3`, `venv/`, `__pycache__/`, `.pytest_cache/`, `.git/`, `staticfiles/`, geçici ZIP dosyaları
