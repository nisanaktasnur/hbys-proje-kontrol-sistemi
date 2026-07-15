from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import ApprovalStatus, Membership, ProjectMembership, Role, UserProfile
from core.demo_defaults import DEMO_PRIMARY_ORG_NAME, DEMO_PRIMARY_PROJECT_NAME
from core.models import Organization, Project
from projects.models import (
    DecisionSource,
    DecisionSupportRecord,
    DecisionStatus,
    GoLiveReadiness,
    ImpactLevel,
    MetricCategory,
    MetricStatus,
    PostGoLiveMetric,
    Priority,
    ProcessArea,
    ProjectRisk,
    ProjectRiskStatus,
    ReadinessStatus,
    RequestRecord,
    RequestStatus,
    RiskCategory,
    RiskLevel,
    UATRecord,
    UATResultStatus,
)
from projects.services.risk_service import apply_risk_to_request


DEMO_HOSPITALS = [
    "Örnek Şehir Hastanesi",
    "Örnek Eğitim ve Araştırma Hastanesi",
    "Örnek Diş Hastanesi",
]

DEMO_PROJECT_NAMES = [
    "HBYS Uygulama Projesi",
    "HBYS Canlı Geçiş Projesi",
    "HBYS Eğitim ve UAT Projesi",
]

DEMO_USERS = [
    ("admin", "Admin123!", "Sistem Yöneticisi", Role.SISTEM_YONETICISI, "Sistem Yöneticisi"),
    ("pm", "Pm123!", "Proje Yöneticisi", Role.PROJE_YONETICISI, "Proje Yöneticisi"),
    ("techlead", "Tech123!", "Teknik Lider", Role.TEKNIK_LIDER, "Teknik Lider"),
    ("manager", "Manager123!", "Yönetici", Role.YONETICI, "Yönetici"),
]

REQUEST_SCENARIOS = [
    ("Poliklinik randevu ekranında performans sorunu", ProcessArea.PERFORMANS, ImpactLevel.YUKSEK, ImpactLevel.ORTA, False, Priority.YUKSEK, "Performans Ekibi"),
    ("Hasta kabul ekranında yetki problemi", ProcessArea.YETKILENDIRME, ImpactLevel.YUKSEK, ImpactLevel.YUKSEK, False, Priority.ACIL, "Yetkilendirme Ekibi"),
    ("Kullanıcı eğitiminde eksik kalan birim", ProcessArea.EGITIM, ImpactLevel.ORTA, ImpactLevel.ORTA, True, Priority.ORTA, "Eğitim Ekibi"),
    ("UAT senaryolarında kapanmamış hata", ProcessArea.UAT, ImpactLevel.YUKSEK, ImpactLevel.YUKSEK, False, Priority.YUKSEK, "UAT Ekibi"),
    ("Veri aktarımı doğrulama bekliyor", ProcessArea.VERI_AKTARIMI, ImpactLevel.YUKSEK, ImpactLevel.ORTA, False, Priority.YUKSEK, "Veri Ekibi"),
    ("Canlı geçiş öncesi kritik ekran yetki problemi", ProcessArea.CANLI_GECIS, ImpactLevel.YUKSEK, ImpactLevel.YUKSEK, False, Priority.ACIL, "Yetkilendirme Ekibi"),
    ("Raporlama ekranında yönetici özet metriği eksik", ProcessArea.RAPORLAMA, ImpactLevel.ORTA, ImpactLevel.DUSUK, True, Priority.ORTA, "Raporlama Ekibi"),
    ("Ameliyathane süreçlerinde kullanıcı rol tanımı eksik", ProcessArea.YETKILENDIRME, ImpactLevel.ORTA, ImpactLevel.YUKSEK, False, Priority.YUKSEK, "Klinik Ekibi"),
    ("Hasta kayıt ekranında alan doğrulama problemi", ProcessArea.OPERASYONEL, ImpactLevel.ORTA, ImpactLevel.YUKSEK, False, Priority.ORTA, "Klinik Ekibi"),
    ("Faturalama sürecinde test senaryosu bekliyor", ProcessArea.UAT, ImpactLevel.ORTA, ImpactLevel.ORTA, True, Priority.ORTA, "Finans Ekibi"),
    ("Klinik kullanıcıların eğitim katılımı düşük", ProcessArea.EGITIM, ImpactLevel.YUKSEK, ImpactLevel.ORTA, True, Priority.YUKSEK, "Eğitim Ekibi"),
    ("Yetkilendirme matrisi tamamlanmadı", ProcessArea.YETKILENDIRME, ImpactLevel.YUKSEK, ImpactLevel.YUKSEK, False, Priority.YUKSEK, "Yetkilendirme Ekibi"),
    ("Eski sistemden aktarılan hasta verilerinde doğrulama bekleniyor", ProcessArea.VERI_AKTARIMI, ImpactLevel.YUKSEK, ImpactLevel.ORTA, False, Priority.YUKSEK, "Veri Ekibi"),
    ("Canlı geçiş destek planı netleşmedi", ProcessArea.CANLI_GECIS, ImpactLevel.YUKSEK, ImpactLevel.YUKSEK, False, Priority.YUKSEK, "Proje Ofisi"),
    ("Yönetici raporlarında açık talep özeti eksik", ProcessArea.RAPORLAMA, ImpactLevel.ORTA, ImpactLevel.DUSUK, True, Priority.DUSUK, "Raporlama Ekibi"),
]


MATRIX_DEMO_RISKS = [
    (
        "Demo matris: Yüksek olasılık ve yüksek etki riski",
        RiskCategory.YETKILENDIRME,
        RiskLevel.YUKSEK,
        RiskLevel.YUKSEK,
        "Yetkilendirme matrisi canlı geçiş öncesi tamamlanmalı.",
        ProjectRiskStatus.DEVAM,
    ),
    (
        "Demo matris: Orta olasılık ve yüksek etki riski",
        RiskCategory.VERI_AKTARIMI,
        RiskLevel.ORTA,
        RiskLevel.YUKSEK,
        "Veri doğrulama kontrol listesi uygulanmalı.",
        ProjectRiskStatus.DEVAM,
    ),
    (
        "Demo matris: Orta olasılık ve orta etki riski",
        RiskCategory.EGITIM,
        RiskLevel.ORTA,
        RiskLevel.ORTA,
        "Eğitim katılım planı güncellenmeli.",
        ProjectRiskStatus.ACIK,
    ),
]

TECHNICAL_DEMO_RISKS = [
    (
        "Demo teknik: Entegrasyon arayüzü gecikmesi",
        RiskCategory.ENTEGRASYON,
        RiskLevel.YUKSEK,
        RiskLevel.YUKSEK,
        "Entegrasyon test ortamı ve API sözleşmesi doğrulanmalı.",
        ProjectRiskStatus.DEVAM,
    ),
    (
        "Demo teknik: Performans darboğazı riski",
        RiskCategory.PERFORMANS,
        RiskLevel.ORTA,
        RiskLevel.YUKSEK,
        "Yoğun saatler için yük testi planlanmalı.",
        ProjectRiskStatus.DEVAM,
    ),
    (
        "Demo teknik: Öncelikli modül yazılım hatası",
        RiskCategory.YAZILIM_HATASI,
        RiskLevel.ORTA,
        RiskLevel.ORTA,
        "Hata düzeltme sprintine alınmalı.",
        ProjectRiskStatus.ACIK,
    ),
]


def _ensure_matrix_risks(project, users, extra_risks=None):
    for idx, (title, cat, prob, impact, mitigation, status) in enumerate(MATRIX_DEMO_RISKS):
        ProjectRisk.objects.update_or_create(
            project=project,
            title=title,
            defaults={
                "description": f"{title} — demo proje riski.",
                "category": cat,
                "probability": prob,
                "impact": impact,
                "mitigation_action": mitigation,
                "contingency_action": "Alternatif geçici çözüm devreye alınmalı.",
                "owner": users["pm"],
                "due_date": timezone.localdate() + timedelta(days=7 - idx),
                "status": status,
                "created_by": users["pm"],
            },
        )
    for idx, (title, cat, prob, impact, mitigation, status) in enumerate(TECHNICAL_DEMO_RISKS):
        ProjectRisk.objects.update_or_create(
            project=project,
            title=title,
            defaults={
                "description": f"{title} — demo teknik risk.",
                "category": cat,
                "probability": prob,
                "impact": impact,
                "mitigation_action": mitigation,
                "contingency_action": "Geçici teknik çözüm uygulanmalı.",
                "owner": users["techlead"],
                "due_date": timezone.localdate() + timedelta(days=5 - idx),
                "status": status,
                "created_by": users["techlead"],
            },
        )
    if extra_risks:
        today = timezone.localdate()
        ProjectRisk.objects.filter(
            project=project,
            title="Kritik iş akışlarında UAT senaryolarının kapanmaması",
        ).delete()
        ProjectRisk.objects.filter(
            project=project,
            title="Demo teknik: Kritik modül yazılım hatası",
        ).delete()
        for idx, (title, cat, prob, impact) in enumerate(extra_risks):
            ProjectRisk.objects.update_or_create(
                project=project,
                title=title,
                defaults={
                    "description": f"{title} — demo proje riski.",
                    "category": cat,
                    "probability": prob,
                    "impact": impact,
                    "mitigation_action": "Planlı aksiyon ve sorumlu ataması yapılmalı.",
                    "contingency_action": "Alternatif geçici çözüm devreye alınmalı.",
                    "owner": users["pm"],
                    "due_date": today + timedelta(days=10 - idx),
                    "status": ProjectRiskStatus.DEVAM if idx < 4 else ProjectRiskStatus.ACIK,
                    "created_by": users["pm"],
                },
            )


def _ensure_request_records(project, users):
    if RequestRecord.objects.filter(project=project).exists():
        return
    today = timezone.localdate()
    statuses = [RequestStatus.ACIK, RequestStatus.DEVAM, RequestStatus.PLANLANDI, RequestStatus.TAMAMLANDI]
    for idx, (title, process, gl_impact, safety, workaround, priority, team) in enumerate(REQUEST_SCENARIOS):
        due = today + timedelta(days=10 - idx * 3)
        status = statuses[idx % len(statuses)]
        record = RequestRecord(
            project=project,
            record_number=f"HBYS-{project.id:02d}-{idx+1:04d}",
            title=title,
            description=f"{title} — örnek demo kaydı.",
            feedback_source="Proje Ekibi",
            process_area=process,
            priority=priority,
            status=status,
            responsible_team=team,
            created_by=users["pm"],
            owner=users["techlead"] if idx % 2 else users["pm"],
            due_date=due,
            go_live_impact=gl_impact,
            has_workaround=workaround,
            affects_patient_or_user_safety=safety,
            operational_impact=ImpactLevel.ORTA,
            created_at=timezone.now() - timedelta(days=idx * 5 + 3),
        )
        if status == RequestStatus.TAMAMLANDI:
            record.completed_at = timezone.now() - timedelta(days=idx)
        apply_risk_to_request(record, process_open_count=idx % 6)
        record.save()


def _ensure_uat_records(project):
    if UATRecord.objects.filter(project=project).exists():
        return
    today = timezone.localdate()
    uat_data = [
        ("Hasta kabul kullanıcı yetkisi testi", ProcessArea.YETKILENDIRME, UATResultStatus.BASARISIZ, RiskLevel.YUKSEK, "Yetkilendirme Ekibi"),
        ("Poliklinik randevu oluşturma senaryosu", ProcessArea.UAT, UATResultStatus.BASARILI, RiskLevel.ORTA, "UAT Ekibi"),
        ("Faturalama kontrol senaryosu", ProcessArea.OPERASYONEL, UATResultStatus.BLOKE, RiskLevel.YUKSEK, "Finans Ekibi"),
        ("Ameliyathane kullanıcı rolü testi", ProcessArea.YETKILENDIRME, UATResultStatus.TEKRAR, RiskLevel.ORTA, "Klinik Ekibi"),
        ("Yönetici raporu doğrulama senaryosu", ProcessArea.RAPORLAMA, UATResultStatus.BASARILI, RiskLevel.DUSUK, "Raporlama Ekibi"),
    ]
    for idx, (name, area, status, sev, team) in enumerate(uat_data):
        UATRecord.objects.create(
            project=project,
            scenario_name=name,
            process_area=area,
            expected_result="Senaryo beklendiği gibi tamamlanmalı.",
            actual_result="Demo test sonucu kaydı.",
            result_status=status,
            severity=sev,
            responsible_team=team,
            tester_name="Demo Test Kullanıcısı",
            tester_role="UAT Tester",
            test_date=today - timedelta(days=14 - idx * 3),
            resolution_note="İyileştirme planı hazırlanmalı." if status != UATResultStatus.BASARILI else "",
        )


def _ensure_readiness(project):
    GoLiveReadiness.objects.update_or_create(
        project=project,
        defaults={
            "education_status": ReadinessStatus.DEVAM,
            "uat_status": ReadinessStatus.DEVAM,
            "data_migration_status": ReadinessStatus.BEKLEMEDE,
            "authorization_status": ReadinessStatus.RISKLI,
            "critical_open_request_status": ReadinessStatus.RISKLI,
            "overall_status": ReadinessStatus.DEVAM,
            "evaluation_note": "Temel hazırlık alanları tamamlanma aşamasında.",
            "recommended_next_step": "Yetkilendirme ve veri aktarımı kontrolleri önceliklendirilmeli.",
        },
    )


def _ensure_decisions(project, users):
    if DecisionSupportRecord.objects.filter(project=project).exists():
        return
    today = timezone.localdate()
    high_req = RequestRecord.objects.filter(project=project, risk_level="Yüksek").first()
    DecisionSupportRecord.objects.create(
        project=project,
        related_request=high_req,
        source=DecisionSource.TALEP,
        title="Yetkilendirme matrisi tamamlanmalı",
        finding="Kritik ekranlarda yetki tanımları eksik.",
        recommendation="Rol matrisi gözden geçirilip UAT öncesi tamamlanmalı.",
        expected_effect="Canlı geçiş öncesi yetki hataları azalır.",
        priority=Priority.YUKSEK,
        owner=users["techlead"],
        responsible_team="Yetkilendirme Ekibi",
        status=DecisionStatus.DEVAM,
        due_date=today - timedelta(days=2),
    )


def _ensure_metrics(project):
    if PostGoLiveMetric.objects.filter(project=project).exists():
        return
    today = timezone.localdate()
    base = today - timedelta(weeks=4)
    metrics = [
        ("Ortalama talep çözüm süresi", MetricCategory.DESTEK, "48", "72", "saat", MetricStatus.HEDEF_ALTI),
        ("İlk hafta açılan destek talebi sayısı", MetricCategory.DESTEK, "25", "40", "adet", MetricStatus.DIKKAT),
        ("Tekrarlayan hata sayısı", MetricCategory.KALITE, "3", "5", "adet", MetricStatus.HEDEFTE),
        ("Eğitim tamamlanma oranı", MetricCategory.EGITIM, "85", "90", "%", MetricStatus.DIKKAT),
        ("SLA içinde kapatılan kayıt oranı", MetricCategory.PERFORMANS, "78", "85", "%", MetricStatus.HEDEF_ALTI),
    ]
    for idx, (name, cat, target, current, unit, status) in enumerate(metrics):
        PostGoLiveMetric.objects.create(
            project=project,
            metric_name=name,
            metric_category=cat,
            target_value=target,
            current_value=current,
            unit=unit,
            status=status,
            measurement_date=base + timedelta(weeks=idx),
            responsible_team="Proje Ofisi",
            evaluation_note="Demo ölçüm kaydı.",
        )


def _ensure_demo_communications(project, users):
    from accounts.models import Role
    from projects.models import CommunicationType, InstructionStatus, ProjectCommunication

    if ProjectCommunication.objects.filter(project=project, title="Demo yönetici mesajı").exists():
        return
    ProjectCommunication.objects.create(
        project=project,
        communication_type=CommunicationType.MESAJ,
        title="Demo yönetici mesajı",
        description="Proje yöneticisinin görmesi için örnek gelen mesaj.",
        sender=users["manager"],
        recipient_role=Role.PROJE_YONETICISI,
        status=InstructionStatus.GONDERILDI,
    )
    ProjectCommunication.objects.create(
        project=project,
        communication_type=CommunicationType.TALIMAT,
        title="Demo teknik talimat",
        description="Teknik lider için örnek gelen talimat.",
        sender=users["manager"],
        recipient_role=Role.TEKNIK_LIDER,
        priority=Priority.YUKSEK,
        due_date=timezone.localdate() + timedelta(days=14),
        status=InstructionStatus.GONDERILDI,
    )


def _seed_primary_project(project, users, include_extended=True):
    _ensure_readiness(project)
    _ensure_request_records(project, users)
    _ensure_decisions(project, users)
    extra = None
    if include_extended:
        extra = [
            ("UAT senaryolarının öncelikli akışlarda kapanmaması", RiskCategory.UAT, RiskLevel.YUKSEK, RiskLevel.YUKSEK),
            ("Canlı geçiş sonrası destek kapasitesinin yetersiz kalması", RiskCategory.DESTEK, RiskLevel.ORTA, RiskLevel.ORTA),
        ]
    _ensure_matrix_risks(project, users, extra_risks=extra)
    _ensure_uat_records(project)
    if include_extended:
        _ensure_metrics(project)


class Command(BaseCommand):
    help = "Geliştirme ortamı için örnek kurum, proje, kullanıcı ve talep verileri oluşturur."

    def handle(self, *args, **options):
        if not settings.DEBUG and not settings.SEED_DEMO_DATA:
            self.stderr.write(
                "Demo veriler yalnızca DEBUG=True veya SEED_DEMO_DATA=True iken oluşturulabilir."
            )
            return

        hospitals = []
        all_projects = []
        statuses = [
            Project.Status.UYGULAMA,
            Project.Status.CANLI_GECIS,
            Project.Status.UAT,
        ]
        for idx, hospital_name in enumerate(DEMO_HOSPITALS):
            org, _ = Organization.objects.get_or_create(
                name=hospital_name,
                defaults={"is_active": True},
            )
            hospitals.append(org)
            for pidx, project_name in enumerate(DEMO_PROJECT_NAMES):
                project, _ = Project.objects.get_or_create(
                    organization=org,
                    name=project_name,
                    defaults={
                        "client_name": f"{hospital_name} Birimi",
                        "status": statuses[pidx],
                        "start_date": date.today() - timedelta(days=120 + idx * 10),
                        "planned_go_live_date": date.today() + timedelta(days=45 - idx * 5),
                    },
                )
                all_projects.append(project)

        users = {}
        for username, password, full_name, role, _label in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username, defaults={"email": f"{username}@ornek.local"})
            if created:
                user.set_password(password)
                user.save()
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={"full_name": full_name, "approval_status": ApprovalStatus.APPROVED},
            )
            profile.approval_status = ApprovalStatus.APPROVED
            profile.full_name = full_name
            profile.save()
            for hospital in hospitals:
                Membership.objects.update_or_create(
                    user=user,
                    organization=hospital,
                    defaults={"role": role, "is_active": True},
                )
            target_projects = all_projects if role == Role.SISTEM_YONETICISI else [
                p for p in all_projects if p.name == DEMO_PROJECT_NAMES[0]
            ]
            if role == Role.YONETICI:
                target_projects = [
                    p for p in all_projects
                    if p.organization_id in (hospitals[0].id, hospitals[1].id)
                ]
            elif role in (Role.PROJE_YONETICISI, Role.TEKNIK_LIDER):
                target_projects = [p for p in all_projects if p.organization_id == hospitals[0].id]
            for proj in target_projects:
                ProjectMembership.objects.update_or_create(
                    user=user,
                    project=proj,
                    defaults={"role": role, "is_active": True},
                )
            users[username] = user

        primary_project = next(
            p for p in all_projects
            if p.organization.name == DEMO_PRIMARY_ORG_NAME and p.name == DEMO_PRIMARY_PROJECT_NAME
        )
        secondary_manager_project = next(
            (
                p for p in all_projects
                if p.organization_id == hospitals[1].id and p.name == DEMO_PRIMARY_PROJECT_NAME
            ),
            None,
        )

        _seed_primary_project(primary_project, users, include_extended=True)
        if secondary_manager_project:
            _seed_primary_project(secondary_manager_project, users, include_extended=False)

        _ensure_demo_communications(primary_project, users)

        self.stdout.write(self.style.SUCCESS("Demo veriler başarıyla oluşturuldu."))
        self.stdout.write("Giriş: admin/Admin123!, pm/Pm123!, techlead/Tech123!, manager/Manager123!")
