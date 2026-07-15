from django.conf import settings
from django.db import models

from core.models import Project, TimeStampedModel


class AIChatSession(TimeStampedModel):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="ai_sessions",
        verbose_name="Proje",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ai_sessions",
        verbose_name="Kullanıcı",
    )

    class Meta:
        verbose_name = "Yapay Zekâ Oturumu"
        verbose_name_plural = "Yapay Zekâ Oturumları"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Oturum {self.pk} — {self.user.username}"


class MessageRole(models.TextChoices):
    USER = "user", "Kullanıcı"
    ASSISTANT = "assistant", "Asistan"


class AIChatMessage(models.Model):
    session = models.ForeignKey(
        AIChatSession,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Oturum",
    )
    role = models.CharField("Rol", max_length=20, choices=MessageRole.choices)
    message = models.TextField("Mesaj")
    created_at = models.DateTimeField("Oluşturulma", auto_now_add=True)

    class Meta:
        verbose_name = "Yapay Zekâ Mesajı"
        verbose_name_plural = "Yapay Zekâ Mesajları"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.get_role_display()}: {self.message[:50]}"
