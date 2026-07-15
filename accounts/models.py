from django.contrib.auth.models import User
from django.db import models

from core.models import Organization, Project, TimeStampedModel


class Role(models.TextChoices):
    SISTEM_YONETICISI = "Sistem Yöneticisi", "Sistem Yöneticisi"
    PROJE_YONETICISI = "Proje Yöneticisi", "Proje Yöneticisi"
    TEKNIK_LIDER = "Teknik Lider", "Teknik Lider"
    YONETICI = "Yönetici", "Yönetici"


class ApprovalStatus(models.TextChoices):
    PENDING = "Onay Bekliyor", "Onay Bekliyor"
    APPROVED = "Onaylı", "Onaylı"
    REJECTED = "Reddedildi", "Reddedildi"


class UserProfile(TimeStampedModel):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name="Kullanıcı",
    )
    full_name = models.CharField("Ad Soyad", max_length=200)
    approval_status = models.CharField(
        "Onay Durumu",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_users",
        verbose_name="Onaylayan",
    )
    approved_at = models.DateTimeField("Onay Tarihi", null=True, blank=True)

    class Meta:
        verbose_name = "Kullanıcı Profili"
        verbose_name_plural = "Kullanıcı Profilleri"

    def __str__(self):
        return self.full_name

    @property
    def is_approved(self):
        return self.approval_status == ApprovalStatus.APPROVED


class Membership(TimeStampedModel):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Kullanıcı",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Kurum",
    )
    role = models.CharField(
        "Rol",
        max_length=30,
        choices=Role.choices,
    )
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        verbose_name = "Üyelik"
        verbose_name_plural = "Üyelikler"
        unique_together = [("user", "organization")]
        indexes = [
            models.Index(fields=["organization", "role"]),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.role}"

    @classmethod
    def get_active_for_user(cls, user):
        return (
            cls.objects.filter(user=user, is_active=True)
            .select_related("organization")
            .first()
        )


class ProjectMembership(TimeStampedModel):
    """Proje bazlı rol ataması — kullanıcının belirli bir projedeki yetkisini tanımlar."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="project_memberships",
        verbose_name="Kullanıcı",
    )
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="Proje",
    )
    role = models.CharField(
        "Rol",
        max_length=30,
        choices=Role.choices,
    )
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        verbose_name = "Proje Üyeliği"
        verbose_name_plural = "Proje Üyelikleri"
        unique_together = [("user", "project")]
        indexes = [
            models.Index(fields=["project", "role"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.user.username} — {self.project.name} ({self.role})"

    @property
    def organization(self):
        return self.project.organization
