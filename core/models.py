from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Oluşturulma", auto_now_add=True)
    updated_at = models.DateTimeField("Güncellenme", auto_now=True)

    class Meta:
        abstract = True


class Organization(TimeStampedModel):
    name = models.CharField("Kurum Adı", max_length=200)
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        verbose_name = "Kurum"
        verbose_name_plural = "Kurumlar"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Project(TimeStampedModel):
    class Status(models.TextChoices):
        PLANLAMA = "Planlama", "Planlama"
        UYGULAMA = "Uygulama", "Uygulama"
        UAT = "UAT", "UAT"
        CANLI_GECIS = "Canlı Geçiş", "Canlı Geçiş"
        TAMAMLANDI = "Tamamlandı", "Tamamlandı"

    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="projects",
        verbose_name="Kurum",
    )
    name = models.CharField("Proje Adı", max_length=200)
    client_name = models.CharField("Müşteri / Kurum Birimi", max_length=200, blank=True)
    status = models.CharField(
        "Durum",
        max_length=30,
        choices=Status.choices,
        default=Status.UYGULAMA,
    )
    start_date = models.DateField("Başlangıç Tarihi", null=True, blank=True)
    planned_go_live_date = models.DateField("Planlanan Canlı Geçiş", null=True, blank=True)

    class Meta:
        verbose_name = "Proje"
        verbose_name_plural = "Projeler"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["organization", "status"]),
        ]

    def __str__(self):
        return self.name


class AuditLog(models.Model):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="audit_logs",
        verbose_name="Kurum",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name="Proje",
    )
    user = models.ForeignKey(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Kullanıcı",
    )
    action = models.CharField("İşlem", max_length=100)
    object_type = models.CharField("Nesne Türü", max_length=100)
    object_id = models.CharField("Nesne Kimliği", max_length=50, blank=True)
    details = models.TextField("Detay", blank=True)
    created_at = models.DateTimeField("Oluşturulma", auto_now_add=True)

    class Meta:
        verbose_name = "Denetim Kaydı"
        verbose_name_plural = "Denetim Kayıtları"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["object_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.action} — {self.object_type}"
