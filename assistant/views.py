from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from accounts.models import Role
from assistant.models import AIChatMessage, AIChatSession, MessageRole
from assistant.providers import build_project_context, get_ai_provider
from core.mixins import PageAccessMixin
from core.utils import get_active_project, get_user_membership, user_is_approved

SUGGESTED_QUESTIONS = {
    Role.PROJE_YONETICISI: [
        "Bugün takip edilmesi gereken talepler hangileri?",
        "Canlı geçiş için eksikler neler?",
        "Geciken kayıtlar hangi ekiplerde yoğunlaşıyor?",
        "Yönetici için proje özeti hazırla.",
    ],
    Role.TEKNIK_LIDER: [
        "Teknik müdahale bekleyen talepler hangileri?",
        "Geçici çözümü olmayan kayıtlar neler?",
        "Hangi UAT senaryoları bloke durumda?",
        "Teknik ekibe atanmış yüksek riskli işler hangileri?",
    ],
    Role.YONETICI: [
        "Projenin genel durumu nedir?",
        "En önemli üç risk hangisi?",
        "Canlı geçiş kararı için engeller nelerdir?",
        "Hedef altında kalan başarı göstergeleri hangileri?",
    ],
    Role.SISTEM_YONETICISI: [
        "Onay bekleyen kullanıcı sayısı nedir?",
        "Aktif kullanıcı ve rol dağılımı nedir?",
        "Son sistem işlemleri nelerdir?",
    ],
}


class ChatView(PageAccessMixin, TemplateView):
    template_name = "assistant/chat.html"
    page_url_name = "assistant:chat"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        project = get_active_project(self.request)
        session = self._get_or_create_session(project)
        role = self.request.membership.role
        ctx["session"] = session
        ctx["messages"] = session.messages.all() if session else []
        ctx["suggested_questions"] = SUGGESTED_QUESTIONS.get(role, SUGGESTED_QUESTIONS[Role.PROJE_YONETICISI])
        ctx["uses_external_ai"] = bool(__import__("django.conf", fromlist=["settings"]).settings.OPENAI_API_KEY)
        return ctx

    def _get_or_create_session(self, project):
        if not project:
            return None
        session_id = self.request.session.get("ai_session_id")
        if session_id:
            session = AIChatSession.objects.filter(
                id=session_id,
                user=self.request.user,
                project=project,
            ).first()
            if session:
                return session
        session = AIChatSession.objects.create(project=project, user=self.request.user)
        self.request.session["ai_session_id"] = session.id
        return session


@login_required
@require_POST
def send_message(request):
    if not user_is_approved(request.user):
        return JsonResponse({"hata": "Onay gerekli"}, status=403)
    membership = get_user_membership(request)
    if not membership:
        return JsonResponse({"hata": "Oturum gerekli"}, status=401)

    project = get_active_project(request)
    if not project:
        return JsonResponse({"hata": "Proje seçili değil"}, status=400)

    question = request.POST.get("question", "").strip()
    if not question:
        return JsonResponse({"hata": "Soru boş olamaz"}, status=400)

    session_id = request.session.get("ai_session_id")
    session = get_object_or_404(
        AIChatSession,
        id=session_id,
        user=request.user,
        project=project,
    )

    AIChatMessage.objects.create(session=session, role=MessageRole.USER, message=question)

    provider = get_ai_provider()
    context = build_project_context(project, role=membership.role)
    answer = provider.generate_response(question, context)

    AIChatMessage.objects.create(session=session, role=MessageRole.ASSISTANT, message=answer)
    session.save()

    if request.headers.get("HX-Request"):
        return render(
            request,
            "assistant/partials/message_list.html",
            {"messages": session.messages.all()},
        )
    return JsonResponse({"yanit": answer})


@login_required
@require_POST
def new_conversation(request):
    project = get_active_project(request)
    if project:
        session = AIChatSession.objects.create(project=project, user=request.user)
        request.session["ai_session_id"] = session.id
    return redirect("assistant:chat")


@login_required
@require_POST
def clear_conversation(request):
    session_id = request.session.get("ai_session_id")
    if session_id:
        AIChatSession.objects.filter(id=session_id, user=request.user).delete()
        request.session.pop("ai_session_id", None)
    return redirect("assistant:chat")
