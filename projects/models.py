from django.conf import settings
from django.db import models
from django.utils import timezone

from core.models import Project, TimeStampedModel


class FeedbackSource(models.TextChoices):
    HASTANE_CALISANI = "Hastane Çalışanı", "Hastane Çalışanı"
    HASTA_YAKINI = "Hasta / Hasta Yakını", "Hasta / Hasta Yakını"
    PROJE_EKIBI = "Proje Ekibi", "Proje Ekibi"
    TEKNIK_EKIP = "Teknik Ekip", "Teknik Ekip"
    YONETICI = "Yönetici", "Yönetici"
    CAGRI_MERKEZI = "Çağrı Merkezi", "Çağrı Merkezi"
    SAHA_ZIYARETI = "Saha Ziyareti", "Saha Ziyareti"
    UAT_GERI_BILDIRIMI = "UAT Geri Bildirimi", "UAT Geri Bildirimi"


class ProcessArea(models.TextChoices):
    TALEP_YONETIMI = "Talep ve Geri Bildirim Yönetimi", "Talep ve Geri Bildirim Yönetimi"
    EGITIM = "Eğitim", "Eğitim"
    UAT = "UAT", "UAT"
    VERI_AKTARIMI = "Veri Aktarımı", "Veri Aktarımı"
    YETKILENDIRME = "Yetkilendirme", "Yetkilendirme"
    PERFORMANS = "Performans", "Performans"
    CANLI_GECIS = "Canlı Geçiş", "Canlı Geçiş"
    RAPORLAMA = "Raporlama", "Raporlama"
    OPERASYONEL = "Operasyonel Kullanım", "Operasyonel Kullanım"


class Priority(models.TextChoices):
    DUSUK = "Düşük", "Düşük"
    ORTA = "Orta", "Orta"
    YUKSEK = "Yüksek", "Yüksek"
    ACIL = "Acil", "Acil"


class RequestStatus(models.TextChoices):
    ACIK = "Açık", "Açık"
    DEVAM = "Devam Ediyor", "Devam Ediyor"
    PLANLANDI = "Planlandı", "Planlandı"
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"


class TechnicalStatus(models.TextChoices):
    ANALIZ = "Analiz Bekliyor", "Analiz Bekliyor"
    PLANLANDI = "Çözüm Planlandı", "Çözüm Planlandı"
    GELISTIRME = "Geliştirme Devam Ediyor", "Geliştirme Devam Ediyor"
    TEST = "Test Bekliyor", "Test Bekliyor"
    TEKRAR_TEST = "Tekrar Test Bekliyor", "Tekrar Test Bekliyor"
    DOGRULANDI = "Çözüm Doğrulandı", "Çözüm Doğrulandı"
    CANLIYA_HAZIR = "Canlıya Hazır", "Canlıya Hazır"
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"
    BLOKE = "Bloke", "Bloke"


class RootCauseStatus(models.TextChoices):
    BEKLEMEDE = "Beklemede", "Beklemede"
    ANALIZ = "Analiz Ediliyor", "Analiz Ediliyor"
    TANIMLANDI = "Tanımlandı", "Tanımlandı"
    DOGRULANDI = "Doğrulandı", "Doğrulandı"


class RetestStatus(models.TextChoices):
    GEREKMIYOR = "Gerekli Değil", "Gerekli Değil"
    BEKLIYOR = "Bekliyor", "Bekliyor"
    PLANLANDI = "Planlandı", "Planlandı"
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"
    BASARISIZ = "Başarısız", "Başarısız"


class ImpactLevel(models.TextChoices):
    DUSUK = "Düşük", "Düşük"
    ORTA = "Orta", "Orta"
    YUKSEK = "Yüksek", "Yüksek"


class RiskLevel(models.TextChoices):
    DUSUK = "Düşük", "Düşük"
    ORTA = "Orta", "Orta"
    YUKSEK = "Yüksek", "Yüksek"


class RequestRecord(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="requests",
        verbose_name="Proje",
    )
    record_number = models.CharField("Kayıt No", max_length=20, unique=True)
    title = models.CharField("Talep Başlığı", max_length=300)
    description = models.TextField("Açıklama")
    feedback_source = models.CharField(
        "Geri Bildirim Kaynağı",
        max_length=50,
        choices=FeedbackSource.choices,
    )
    process_area = models.CharField(
        "İlgili Süreç",
        max_length=60,
        choices=ProcessArea.choices,
    )
    priority = models.CharField(
        "Öncelik",
        max_length=20,
        choices=Priority.choices,
        default=Priority.ORTA,
    )
    status = models.CharField(
        "Durum",
        max_length=30,
        choices=RequestStatus.choices,
        default=RequestStatus.ACIK,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_requests",
        verbose_name="Sorumlu Kullanıcı",
    )
    responsible_team = models.CharField("Sorumlu Ekip", max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_requests",
        verbose_name="Oluşturan",
    )
    due_date = models.DateField("Hedef Kapanış Tarihi", null=True, blank=True)
    completed_at = models.DateTimeField("Tamamlanma", null=True, blank=True)
    go_live_impact = models.CharField(
        "Canlı Geçiş Etkisi",
        max_length=20,
        choices=ImpactLevel.choices,
        default=ImpactLevel.ORTA,
    )
    has_workaround = models.BooleanField("Geçici Çözüm Var mı?", default=False)
    affects_patient_or_user_safety = models.CharField(
        "Kullanıcı/Hasta Güvenliği Etkisi",
        max_length=20,
        choices=ImpactLevel.choices,
        default=ImpactLevel.DUSUK,
    )
    operational_impact = models.CharField(
        "Operasyonel Etki",
        max_length=20,
        choices=ImpactLevel.choices,
        default=ImpactLevel.ORTA,
    )
    risk_level = models.CharField(
        "Risk Seviyesi",
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.ORTA,
    )
    internal_risk_score = models.PositiveIntegerField("Dahili Risk Skoru", default=0)
    evaluated_factors = models.JSONField("Değerlendirme Unsurları", default=list, blank=True)
    evaluation_note = models.TextField("Sistem Değerlendirme Notu", blank=True)
    recommended_action = models.TextField("Önerilen Aksiyon", blank=True)
    solution_note = models.TextField("Çözüm Notu", blank=True)
    technical_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="technical_requests",
        verbose_name="Teknik Sorumlu",
    )
    technical_status = models.CharField(
        "Teknik Durum",
        max_length=40,
        choices=TechnicalStatus.choices,
        blank=True,
    )
    root_cause_status = models.CharField(
        "Kök Neden Durumu",
        max_length=30,
        choices=RootCauseStatus.choices,
        blank=True,
    )
    retest_status = models.CharField(
        "Tekrar Test Durumu",
        max_length=30,
        choices=RetestStatus.choices,
        blank=True,
    )

    class Meta:
        verbose_name = "Talep Kaydı"
        verbose_name_plural = "Talep Kayıtları"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "risk_level"]),
            models.Index(fields=["project", "process_area"]),
            models.Index(fields=["project", "due_date"]),
            models.Index(fields=["record_number"]),
        ]

    def __str__(self):
        return f"{self.record_number} — {self.title}"

    @property
    def is_overdue(self):
        if not self.due_date or self.status == RequestStatus.TAMAMLANDI:
            return False
        return self.due_date < timezone.localdate()

    @property
    def organization(self):
        return self.project.organization


class DecisionStatus(models.TextChoices):
    BEKLEMEDE = "Beklemede", "Beklemede"
    DEVAM = "Devam Ediyor", "Devam Ediyor"
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"
    IPTAL = "İptal", "İptal"


class DecisionSource(models.TextChoices):
    TALEP = "Talep", "Talep"
    PROJE_RISKI = "Proje Riski", "Proje Riski"
    UAT_BULGUSU = "UAT Bulgusu", "UAT Bulgusu"
    CANLI_GECIS_METRIK = "Canlı Geçiş Sonrası Metrik", "Canlı Geçiş Sonrası Metrik"
    YONETICI = "Yönetici Değerlendirmesi", "Yönetici Değerlendirmesi"


class ProjectRiskStatus(models.TextChoices):
    ACIK = "Açık", "Açık"
    DEVAM = "Devam Ediyor", "Devam Ediyor"
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"
    IPTAL = "İptal", "İptal"


class RiskCategory(models.TextChoices):
    TEKNIK = "Teknik", "Teknik"
    OPERASYONEL = "Operasyonel", "Operasyonel"
    ORGANIZASYONEL = "Organizasyonel", "Organizasyonel"
    CANLI_GECIS = "Canlı Geçiş", "Canlı Geçiş"
    UAT = "UAT", "UAT"
    VERI_AKTARIMI = "Veri Aktarımı", "Veri Aktarımı"
    YETKILENDIRME = "Yetkilendirme", "Yetkilendirme"
    EGITIM = "Eğitim", "Eğitim"
    DESTEK = "Destek Kapasitesi", "Destek Kapasitesi"
    YAZILIM_HATASI = "Yazılım Hatası", "Yazılım Hatası"
    PERFORMANS = "Performans", "Performans"
    ENTEGRASYON = "Entegrasyon", "Entegrasyon"
    RAPORLAMA = "Raporlama", "Raporlama"
    TEST_UAT = "Test/UAT", "Test/UAT"
    CANLI_GECIS_TEKNIK = "Canlı Geçiş Teknik Hazırlık", "Canlı Geçiş Teknik Hazırlık"
    ALTYAPI = "Altyapı", "Altyapı"


TECHNICAL_RISK_CATEGORIES = {
    RiskCategory.YAZILIM_HATASI,
    RiskCategory.PERFORMANS,
    RiskCategory.YETKILENDIRME,
    RiskCategory.VERI_AKTARIMI,
    RiskCategory.ENTEGRASYON,
    RiskCategory.RAPORLAMA,
    RiskCategory.TEST_UAT,
    RiskCategory.CANLI_GECIS_TEKNIK,
    RiskCategory.ALTYAPI,
    RiskCategory.TEKNIK,
}


class UATResultStatus(models.TextChoices):
    BASARILI = "Başarılı", "Başarılı"
    BASARISIZ = "Başarısız", "Başarısız"
    BLOKE = "Bloke", "Bloke"
    TEKRAR = "Tekrar Test Bekliyor", "Tekrar Test Bekliyor"


class MetricStatus(models.TextChoices):
    HEDEFTE = "Hedefte", "Hedefte"
    DIKKAT = "Dikkat Gerekli", "Dikkat Gerekli"
    HEDEF_ALTI = "Hedef Altında", "Hedef Altında"


class MetricCategory(models.TextChoices):
    DESTEK = "Destek Operasyonu", "Destek Operasyonu"
    KALITE = "Kalite ve Tekrar", "Kalite ve Tekrar"
    EGITIM = "Eğitim ve Kullanım", "Eğitim ve Kullanım"
    PERFORMANS = "Performans ve SLA", "Performans ve SLA"
    VERI = "Veri ve Yetkilendirme", "Veri ve Yetkilendirme"
    MEMNUNIYET = "Kullanıcı Geri Bildirimi", "Kullanıcı Geri Bildirimi"


class ProjectRisk(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="project_risks",
        verbose_name="Proje",
    )
    title = models.CharField("Risk Başlığı", max_length=300)
    description = models.TextField("Risk Açıklaması")
    category = models.CharField(
        "Risk Kategorisi",
        max_length=60,
        choices=RiskCategory.choices,
    )
    probability = models.CharField(
        "Olasılık",
        max_length=20,
        choices=RiskLevel.choices,
    )
    impact = models.CharField(
        "Etki Seviyesi",
        max_length=20,
        choices=RiskLevel.choices,
    )
    risk_level = models.CharField(
        "Risk Seviyesi",
        max_length=20,
        choices=RiskLevel.choices,
    )
    mitigation_action = models.TextField("Önleyici Aksiyon", blank=True)
    contingency_action = models.TextField("Gerçekleşme Durumunda Aksiyon", blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_project_risks",
        verbose_name="Sorumlu",
    )
    due_date = models.DateField("Hedef Tarih", null=True, blank=True)
    status = models.CharField(
        "Durum",
        max_length=30,
        choices=ProjectRiskStatus.choices,
        default=ProjectRiskStatus.ACIK,
    )
    related_request = models.ForeignKey(
        "RequestRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_project_risks",
        verbose_name="İlgili Talep",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_project_risks",
        verbose_name="Oluşturan",
    )

    class Meta:
        verbose_name = "Proje Riski"
        verbose_name_plural = "Proje Riskleri"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["project", "risk_level"]),
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "due_date"]),
        ]

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        if not self.due_date or self.status == ProjectRiskStatus.TAMAMLANDI:
            return False
        return self.due_date < timezone.localdate()

    def save(self, *args, **kwargs):
        from projects.services.risk_matrix_service import calculate_project_risk_level

        self.risk_level = calculate_project_risk_level(self.probability, self.impact)
        super().save(*args, **kwargs)


class UATRecord(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="uat_records",
        verbose_name="Proje",
    )
    scenario_name = models.CharField("Senaryo Adı", max_length=300)
    process_area = models.CharField(
        "İlgili Süreç",
        max_length=60,
        choices=ProcessArea.choices,
    )
    expected_result = models.TextField("Beklenen Sonuç")
    actual_result = models.TextField("Gerçekleşen Sonuç", blank=True)
    result_status = models.CharField(
        "Sonuç Durumu",
        max_length=30,
        choices=UATResultStatus.choices,
    )
    severity = models.CharField(
        "Önem Düzeyi",
        max_length=20,
        choices=RiskLevel.choices,
        default=RiskLevel.ORTA,
    )
    responsible_team = models.CharField("Sorumlu Ekip", max_length=100)
    tester_name = models.CharField("Test Eden", max_length=100, blank=True)
    tester_role = models.CharField("Test Eden Rol", max_length=100, blank=True)
    test_date = models.DateField("Test Tarihi", null=True, blank=True)
    resolution_note = models.TextField("Çözüm Notu", blank=True)
    root_cause_note = models.TextField("Kök Neden Notu", blank=True)
    retest_status = models.CharField(
        "Tekrar Test Durumu",
        max_length=30,
        choices=RetestStatus.choices,
        blank=True,
    )
    related_request = models.ForeignKey(
        "RequestRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uat_records",
        verbose_name="İlgili Talep",
    )

    class Meta:
        verbose_name = "UAT Kaydı"
        verbose_name_plural = "UAT Kayıtları"
        ordering = ["-test_date", "-updated_at"]
        indexes = [
            models.Index(fields=["project", "result_status"]),
            models.Index(fields=["project", "severity"]),
        ]

    def __str__(self):
        return self.scenario_name

    @property
    def blocks_go_live(self):
        return self.result_status in (
            UATResultStatus.BASARISIZ,
            UATResultStatus.BLOKE,
            UATResultStatus.TEKRAR,
        ) and self.severity == RiskLevel.YUKSEK


class PostGoLiveMetric(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="post_go_live_metrics",
        verbose_name="Proje",
    )
    metric_name = models.CharField("Gösterge Adı", max_length=200)
    metric_category = models.CharField(
        "Gösterge Kategorisi",
        max_length=60,
        choices=MetricCategory.choices,
    )
    target_value = models.CharField("Hedef Değer", max_length=100)
    current_value = models.CharField("Güncel Değer", max_length=100)
    unit = models.CharField("Birim", max_length=50, blank=True)
    status = models.CharField(
        "Durum",
        max_length=30,
        choices=MetricStatus.choices,
    )
    measurement_date = models.DateField("Ölçüm Tarihi")
    responsible_team = models.CharField("Sorumlu Ekip", max_length=100)
    evaluation_note = models.TextField("Değerlendirme Notu", blank=True)

    class Meta:
        verbose_name = "Canlı Geçiş Sonrası Gösterge"
        verbose_name_plural = "Canlı Geçiş Sonrası Göstergeler"
        ordering = ["-measurement_date", "-updated_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "measurement_date"]),
        ]

    def __str__(self):
        return self.metric_name


class DecisionSupportRecord(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="decisions",
        verbose_name="Proje",
    )
    related_request = models.ForeignKey(
        RequestRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
        verbose_name="İlgili Talep",
    )
    related_project_risk = models.ForeignKey(
        ProjectRisk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
        verbose_name="İlgili Proje Riski",
    )
    related_uat_record = models.ForeignKey(
        UATRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
        verbose_name="İlgili UAT Kaydı",
    )
    related_post_go_live_metric = models.ForeignKey(
        PostGoLiveMetric,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decisions",
        verbose_name="İlgili Canlı Geçiş Göstergesi",
    )
    source = models.CharField(
        "Kaynak",
        max_length=40,
        choices=DecisionSource.choices,
        default=DecisionSource.YONETICI,
    )
    source_key = models.CharField("Kaynak Anahtarı", max_length=120, blank=True, db_index=True)
    title = models.CharField("Başlık", max_length=300)
    finding = models.TextField("Tespit")
    recommendation = models.TextField("Önerilen Karar")
    expected_effect = models.TextField("Beklenen Etki", blank=True)
    priority = models.CharField(
        "Öncelik",
        max_length=20,
        choices=Priority.choices,
        default=Priority.ORTA,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_decisions",
        verbose_name="Sorumlu",
    )
    responsible_team = models.CharField("Sorumlu Ekip", max_length=100, blank=True)
    status = models.CharField(
        "Durum",
        max_length=30,
        choices=DecisionStatus.choices,
        default=DecisionStatus.BEKLEMEDE,
    )
    due_date = models.DateField("Hedef Tarih", null=True, blank=True)
    notes = models.TextField("Notlar", blank=True)

    class Meta:
        verbose_name = "Karar Destek Kaydı"
        verbose_name_plural = "Karar Destek Kayıtları"
        ordering = ["-updated_at"]
        indexes = [
            models.Index(fields=["project", "status"]),
            models.Index(fields=["project", "due_date"]),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        from projects.services.decision_suggestion_service import build_decision_source_key

        self.source_key = build_decision_source_key(self)
        super().save(*args, **kwargs)

    @property
    def is_overdue(self):
        if not self.due_date or self.status == DecisionStatus.TAMAMLANDI:
            return False
        return self.due_date < timezone.localdate()


class ReadinessStatus(models.TextChoices):
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"
    DEVAM = "Devam Ediyor", "Devam Ediyor"
    EKSIK = "Eksik", "Eksik"
    RISKLI = "Riskli", "Riskli"
    BEKLEMEDE = "Beklemede", "Beklemede"


class GoLiveReadiness(TimeStampedModel):
    project = models.OneToOneField(
        Project,
        on_delete=models.CASCADE,
        related_name="go_live_readiness",
        verbose_name="Proje",
    )
    education_status = models.CharField(
        "Eğitim Durumu",
        max_length=30,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.DEVAM,
    )
    uat_status = models.CharField(
        "UAT Durumu",
        max_length=30,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.DEVAM,
    )
    data_migration_status = models.CharField(
        "Veri Aktarımı",
        max_length=30,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.BEKLEMEDE,
    )
    authorization_status = models.CharField(
        "Yetkilendirme Kontrolü",
        max_length=30,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.DEVAM,
    )
    critical_open_request_status = models.CharField(
        "Kritik Açık Kayıt",
        max_length=30,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.RISKLI,
    )
    overall_status = models.CharField(
        "Genel Durum",
        max_length=30,
        choices=ReadinessStatus.choices,
        default=ReadinessStatus.DEVAM,
    )
    evaluation_note = models.TextField("Değerlendirme Notu", blank=True)
    recommended_next_step = models.TextField("Önerilen Sonraki Adım", blank=True)

    class Meta:
        verbose_name = "Canlı Geçiş Hazırlığı"
        verbose_name_plural = "Canlı Geçiş Hazırlıkları"

    def __str__(self):
        return f"{self.project.name} — Canlı Geçiş"


class RequestActivity(models.Model):
    request = models.ForeignKey(
        RequestRecord,
        on_delete=models.CASCADE,
        related_name="activities",
        verbose_name="Talep",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Kullanıcı",
    )
    action = models.CharField("İşlem", max_length=200)
    details = models.TextField("Detay", blank=True)
    created_at = models.DateTimeField("Tarih", auto_now_add=True)

    class Meta:
        verbose_name = "Talep Aktivitesi"
        verbose_name_plural = "Talep Aktiviteleri"
        ordering = ["-created_at"]


class CommunicationType(models.TextChoices):
    MESAJ = "Mesaj", "Mesaj"
    TALIMAT = "Talimat", "Talimat"


class InstructionStatus(models.TextChoices):
    GONDERILDI = "Gönderildi", "Gönderildi"
    GORULDU = "Görüldü", "Görüldü"
    DEVAM = "Devam Ediyor", "Devam Ediyor"
    TAMAMLANDI = "Tamamlandı", "Tamamlandı"
    IPTAL = "İptal Edildi", "İptal Edildi"


class ProjectCommunication(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="communications",
        verbose_name="Proje",
    )
    communication_type = models.CharField(
        "Tür",
        max_length=20,
        choices=CommunicationType.choices,
        default=CommunicationType.MESAJ,
    )
    title = models.CharField("Başlık", max_length=300)
    description = models.TextField("Açıklama")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sent_communications",
        verbose_name="Gönderen",
    )
    recipient_role = models.CharField("Alıcı Rol", max_length=30, blank=True)
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_communications",
        verbose_name="Alıcı Kullanıcı",
    )
    related_request = models.ForeignKey(
        RequestRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communications",
        verbose_name="İlgili Talep",
    )
    related_project_risk = models.ForeignKey(
        ProjectRisk,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communications",
        verbose_name="İlgili Risk",
    )
    related_uat_record = models.ForeignKey(
        UATRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communications",
        verbose_name="İlgili UAT",
    )
    related_decision = models.ForeignKey(
        DecisionSupportRecord,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communications",
        verbose_name="İlgili Karar",
    )
    priority = models.CharField(
        "Öncelik",
        max_length=20,
        choices=Priority.choices,
        default=Priority.ORTA,
    )
    due_date = models.DateField("Hedef Tarih", null=True, blank=True)
    status = models.CharField(
        "Durum",
        max_length=30,
        choices=InstructionStatus.choices,
        default=InstructionStatus.GONDERILDI,
    )
    is_read = models.BooleanField("Okundu", default=False)
    read_at = models.DateTimeField("Okunma Zamanı", null=True, blank=True)
    completion_note = models.TextField("Tamamlanma Notu", blank=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="replies",
        verbose_name="Üst İletişim",
    )

    class Meta:
        verbose_name = "Proje İletişimi"
        verbose_name_plural = "Proje İletişimleri"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["project", "communication_type"]),
            models.Index(fields=["project", "status"]),
        ]

    def __str__(self):
        return self.title

    @property
    def organization(self):
        return self.project.organization
