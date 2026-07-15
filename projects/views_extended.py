from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from core.context import get_accessible_projects, set_active_context
from core.mixins import PageAccessMixin
from core.permissions import (
    can_manage_technical_actions,
    can_manage_technical_risks,
    can_send_communication,
    can_update_uat_technical,
    require_permission,
)
from core.utils import get_user_membership, log_audit
from projects.forms import (
    CommunicationForm,
    CommunicationReplyForm,
    CommunicationStatusForm,
    ProjectRiskForm,
    TechnicalRequestUpdateForm,
    UATTechnicalUpdateForm,
)
from projects.models import (
    CommunicationType,
    InstructionStatus,
    ProjectCommunication,
    ProjectRisk,
    RequestRecord,
    RequestStatus,
    RiskLevel,
    TECHNICAL_RISK_CATEGORIES,
    UATRecord,
)
from projects.services.communication_service import (
    communication_inbox_summary,
    communication_thread_root,
    completed_instructions,
    create_reply,
    incoming_instructions,
    incoming_messages,
    manager_communication_summary,
    mark_communication_read,
    pending_instructions,
    sent_communications,
    unread_communications,
    user_can_update_communication,
    user_can_view_communication,
    user_is_recipient,
)
from projects.services.manager_strategic_service import manager_strategic_summary
from projects.services.risk_matrix_service import matrix_risk_details, project_risk_summary
from projects.services.technical_service import (
    technical_actions,
    technical_dashboard_stats,
    technical_risks,
    technical_uat_findings,
    technical_work_list,
)
from projects.services.uat_summary_service import uat_summary
from projects.views import _project_queryset


def _pending_for_request(request, project):
    if not project:
        return []
    return list(
        pending_instructions(
            request.user,
            project,
            request.membership.role if request.membership else None,
        )[:8]
    )


def _technical_risk_form(project, organization, data=None, instance=None):
    form = ProjectRiskForm(
        data,
        instance=instance,
        project=project,
        organization=organization,
    )
    tech_values = {category.value for category in TECHNICAL_RISK_CATEGORIES}
    form.fields["category"].choices = [
        choice for choice in form.fields["category"].choices
        if not choice[0] or choice[0] in tech_values
    ]
    return form


class ManagerPanelView(PageAccessMixin, TemplateView):
    template_name = "projects/manager_panel.html"
    page_url_name = "projects:manager_panel"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs, project = _project_queryset(self.request)
        from projects.models import GoLiveReadiness

        readiness = GoLiveReadiness.objects.filter(project=project).first() if project else None
        ctx.update(manager_strategic_summary(qs, project, readiness))
        ctx["read_only_dashboard"] = True
        ctx["pending_instructions"] = _pending_for_request(self.request, project)
        ctx["communication_summary"] = manager_communication_summary(self.request.user, project)
        return ctx


class TechnicalWorkListView(PageAccessMixin, TemplateView):
    template_name = "projects/technical_work_list.html"
    page_url_name = "projects:technical_work_list"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        qs, project = _project_queryset(self.request)
        status = self.request.GET.get("status") or None
        risk_level = self.request.GET.get("risk_level") or None
        mine = self.request.GET.get("mine") == "1"
        filtered = technical_work_list(
            qs,
            user=self.request.user if mine else None,
            status=status,
            risk_level=risk_level,
        )
        paginator = Paginator(filtered, 20)
        ctx["page_obj"] = paginator.get_page(self.request.GET.get("page"))
        ctx["status_choices"] = RequestStatus.choices
        ctx["risk_choices"] = RiskLevel.choices
        ctx["filter_status"] = status
        ctx["filter_risk"] = risk_level
        ctx["filter_mine"] = mine
        ctx["pending_instructions"] = _pending_for_request(self.request, project)
        return ctx


class TechnicalRisksView(PageAccessMixin, TemplateView):
    template_name = "projects/technical_risks.html"
    page_url_name = "projects:technical_risks"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, project = _project_queryset(self.request)
        pr_qs = technical_risks(project)
        ctx["technical_risks"] = pr_qs
        ctx["project_risk_summary"] = project_risk_summary(pr_qs)
        ctx["matrix_details"] = matrix_risk_details(pr_qs, categories=TECHNICAL_RISK_CATEGORIES)
        ctx["can_manage_technical_risks"] = can_manage_technical_risks(self.request.user, project)
        if project:
            ctx["project_risk_form"] = _technical_risk_form(
                project,
                self.request.membership.organization,
            )
        ctx["pending_instructions"] = _pending_for_request(self.request, project)
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        require_permission(can_manage_technical_risks(request.user, project))
        if not project:
            return redirect("projects:technical_risks")
        edit_pk = request.POST.get("edit_pk")
        instance = None
        if edit_pk:
            instance = get_object_or_404(ProjectRisk, pk=edit_pk, project=project)
        form = _technical_risk_form(
            project,
            request.membership.organization,
            data=request.POST,
            instance=instance,
        )
        if form.is_valid():
            tech_values = {category.value for category in TECHNICAL_RISK_CATEGORIES}
            category = form.cleaned_data.get("category")
            if category and category not in tech_values:
                messages.error(request, "Yalnızca teknik risk kategorileri seçilebilir.")
            else:
                risk = form.save(commit=False)
                risk.project = project
                if not risk.pk:
                    risk.created_by = request.user
                risk.save()
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Teknik Proje Riski",
                    "ProjectRisk",
                    risk.pk,
                    risk.title,
                    project,
                )
                messages.success(request, "Teknik proje riski kaydedildi.")
        else:
            messages.error(request, "Risk kaydı doğrulanamadı.")
        return redirect("projects:technical_risks")


class TechnicalUATView(PageAccessMixin, TemplateView):
    template_name = "projects/technical_uat.html"
    page_url_name = "projects:technical_uat"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, project = _project_queryset(self.request)
        uat_qs = technical_uat_findings(project)
        ctx["uat_records"] = uat_qs
        ctx["uat_summary"] = uat_summary(uat_qs)
        ctx["can_update_uat_technical"] = can_update_uat_technical(self.request.user, project)
        ctx["uat_technical_form"] = UATTechnicalUpdateForm()
        ctx["pending_instructions"] = _pending_for_request(self.request, project)
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        require_permission(can_update_uat_technical(request.user, project))
        uat = get_object_or_404(
            UATRecord,
            pk=request.POST.get("uat_id"),
            project__in=get_accessible_projects(request.user),
        )
        form = UATTechnicalUpdateForm(request.POST, instance=uat)
        if form.is_valid():
            form.save()
            log_audit(
                request.user,
                request.membership.organization,
                "UAT Teknik Güncelleme",
                "UATRecord",
                uat.pk,
                uat.scenario_name,
                project,
            )
            messages.success(request, "UAT teknik alanları güncellendi.")
        else:
            messages.error(request, "UAT güncellemesi doğrulanamadı.")
        return redirect("projects:technical_uat")


class TechnicalActionsView(PageAccessMixin, TemplateView):
    template_name = "projects/technical_actions.html"
    page_url_name = "projects:technical_actions"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, project = _project_queryset(self.request)
        ctx["action_records"] = technical_actions(project, self.request.user)
        ctx["can_manage_technical_actions"] = can_manage_technical_actions(
            self.request.user, project
        )
        ctx["technical_form"] = TechnicalRequestUpdateForm(project=project)
        ctx["pending_instructions"] = _pending_for_request(self.request, project)
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        require_permission(can_manage_technical_actions(request.user, project))
        record = RequestRecord.objects.filter(
            pk=request.POST.get("record_id"),
            project=project,
        ).first()
        if record:
            form = TechnicalRequestUpdateForm(request.POST, instance=record, project=project)
            if form.is_valid():
                form.save()
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Teknik Aksiyon Güncelleme",
                    "RequestRecord",
                    record.pk,
                    record.title,
                    project,
                )
                messages.success(request, "Teknik aksiyon güncellendi.")
        return redirect("projects:technical_actions")


class CommunicationCenterView(PageAccessMixin, TemplateView):
    template_name = "projects/communication_center.html"
    page_url_name = "projects:communication_center"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        _, project = _project_queryset(self.request)
        membership = self.request.membership
        role = membership.role if membership else None
        ctx["incoming_messages"] = (
            list(incoming_messages(self.request.user, project, role))
            if project
            else []
        )
        ctx["incoming_instructions"] = (
            list(incoming_instructions(self.request.user, project, role))
            if project
            else []
        )
        ctx["sent_communications"] = (
            list(sent_communications(self.request.user, project))
            if project
            else []
        )
        ctx["completed_instructions"] = (
            list(completed_instructions(self.request.user, project, role))
            if project
            else []
        )
        ctx["unread_communications"] = (
            list(unread_communications(self.request.user, project, role))
            if project
            else []
        )
        ctx["active_tab"] = self.request.GET.get("tab", "gelen-mesajlar")
        ctx["message_form"] = CommunicationForm(
            project=project,
            comm_type=CommunicationType.MESAJ,
            initial={"communication_type": CommunicationType.MESAJ},
        )
        ctx["instruction_form"] = CommunicationForm(
            project=project,
            comm_type=CommunicationType.TALIMAT,
            initial={"communication_type": CommunicationType.TALIMAT},
        )
        ctx["status_form"] = CommunicationStatusForm()
        ctx["instruction_status_choices"] = InstructionStatus.choices
        ctx["can_send_communication"] = can_send_communication(self.request.user, project)
        ctx["pending_instructions"] = _pending_for_request(self.request, project)
        ctx["active_organization"] = membership.organization if membership else None
        ctx["active_project"] = project
        return ctx

    def post(self, request, *args, **kwargs):
        _, project = _project_queryset(request)
        action = request.POST.get("action", "create")

        if action == "update_status":
            comm = get_object_or_404(
                ProjectCommunication,
                pk=request.POST.get("communication_id"),
                project__in=get_accessible_projects(request.user),
            )
            if not user_can_update_communication(request.user, comm, request.membership):
                raise PermissionDenied
            form = CommunicationStatusForm(request.POST, instance=comm)
            if form.is_valid():
                updated = form.save(commit=False)
                if updated.status == InstructionStatus.GORULDU and not updated.is_read:
                    updated.is_read = True
                updated.save()
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Talimat Durum Güncelleme",
                    "ProjectCommunication",
                    comm.pk,
                    comm.title,
                    project,
                )
                messages.success(request, "Talimat durumu güncellendi.")
            else:
                messages.error(request, "Talimat durumu güncellenemedi.")
            return redirect("projects:communication_center")

        if action == "mark_read":
            comm = get_object_or_404(
                ProjectCommunication,
                pk=request.POST.get("communication_id"),
                project__in=get_accessible_projects(request.user),
            )
            if not user_can_update_communication(request.user, comm, request.membership):
                raise PermissionDenied
            comm.is_read = True
            comm.read_at = timezone.now()
            if comm.status == InstructionStatus.GONDERILDI:
                comm.status = InstructionStatus.GORULDU
            comm.save(update_fields=["is_read", "read_at", "status", "updated_at"])
            messages.success(request, "Mesaj okundu olarak işaretlendi.")
            return redirect("projects:communication_center")

        require_permission(can_send_communication(request.user, project))
        if not project:
            return redirect("projects:communication_center")
        form = CommunicationForm(
            request.POST,
            project=project,
            comm_type=request.POST.get("communication_type", CommunicationType.MESAJ),
        )
        if form.is_valid():
            comm = form.save(commit=False)
            comm.project = project
            comm.sender = request.user
            if comm.communication_type == CommunicationType.TALIMAT:
                comm.status = InstructionStatus.GONDERILDI
            comm.save()
            log_audit(
                request.user,
                request.membership.organization,
                "Proje İletişimi",
                "ProjectCommunication",
                comm.pk,
                comm.title,
                project,
            )
            if comm.communication_type == CommunicationType.TALIMAT:
                messages.success(request, "Talimat gönderildi.")
            else:
                messages.success(request, "Mesaj gönderildi.")
            return redirect("projects:communication_center")
        messages.error(request, "Gönderim doğrulanamadı. Alıcı seçildiğinden emin olun.")
        ctx = self.get_context_data(**kwargs)
        comm_type = request.POST.get("communication_type", CommunicationType.MESAJ)
        if comm_type == CommunicationType.TALIMAT:
            ctx["instruction_form"] = form
        else:
            ctx["message_form"] = form
        return render(request, self.template_name, ctx)


class CommunicationDetailView(PageAccessMixin, TemplateView):
    template_name = "projects/communication_detail.html"
    page_url_name = "projects:communication_detail"

    def _load_root(self):
        comm = get_object_or_404(
            ProjectCommunication.objects.select_related(
                "sender",
                "sender__profile",
                "recipient_user",
                "recipient_user__profile",
                "project",
                "project__organization",
                "related_request",
                "related_project_risk",
                "related_uat_record",
                "related_decision",
            ),
            pk=self.kwargs["pk"],
            project__in=get_accessible_projects(self.request.user),
        )
        root = communication_thread_root(comm)
        if not user_can_view_communication(self.request.user, root, self.request.membership):
            raise Http404()
        return root, comm

    def dispatch(self, request, *args, **kwargs):
        root, comm = self._load_root()
        if root.pk != comm.pk and request.method == "GET":
            return redirect("projects:communication_detail", pk=root.pk)
        self.communication_root = root
        if request.method == "GET":
            mark_communication_read(root, request.user, request.membership)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        root = self.communication_root
        root.refresh_from_db()
        ctx["communication"] = root
        ctx["replies"] = list(
            root.replies.select_related("sender__profile").order_by("created_at")
        )
        ctx["reply_form"] = CommunicationReplyForm()
        ctx["status_form"] = (
            CommunicationStatusForm(instance=root)
            if root.communication_type == CommunicationType.TALIMAT
            else None
        )
        ctx["instruction_status_choices"] = InstructionStatus.choices
        ctx["can_reply"] = user_can_view_communication(
            self.request.user, root, self.request.membership
        )
        ctx["is_recipient"] = user_is_recipient(
            self.request.user, root, self.request.membership
        )
        ctx["is_sender"] = root.sender_id == self.request.user.id
        return ctx

    def post(self, request, *args, **kwargs):
        root = self.communication_root
        action = request.POST.get("action")

        if action == "reply":
            form = CommunicationReplyForm(request.POST)
            if form.is_valid():
                reply = create_reply(
                    root,
                    request.user,
                    form.cleaned_data["description"],
                    request.membership,
                )
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Proje İletişim Yanıtı",
                    "ProjectCommunication",
                    reply.pk,
                    reply.title,
                    root.project,
                )
                messages.success(request, "Yanıt gönderildi.")
            else:
                messages.error(request, "Yanıt gönderilemedi.")
            return redirect("projects:communication_detail", pk=root.pk)

        if action == "update_status":
            if root.communication_type != CommunicationType.TALIMAT:
                raise PermissionDenied
            if not user_can_update_communication(request.user, root, request.membership):
                raise PermissionDenied
            form = CommunicationStatusForm(request.POST, instance=root)
            if form.is_valid():
                updated = form.save(commit=False)
                if updated.status == InstructionStatus.GORULDU and not updated.is_read:
                    updated.is_read = True
                    updated.read_at = timezone.now()
                updated.save()
                log_audit(
                    request.user,
                    request.membership.organization,
                    "Talimat Durum Güncelleme",
                    "ProjectCommunication",
                    root.pk,
                    root.title,
                    root.project,
                )
                messages.success(request, "Talimat durumu güncellendi.")
            else:
                messages.error(request, "Talimat durumu güncellenemedi.")
            return redirect("projects:communication_detail", pk=root.pk)

        if action == "mark_read":
            mark_communication_read(root, request.user, request.membership)
            messages.success(request, "Okundu olarak işaretlendi.")
            return redirect("projects:communication_detail", pk=root.pk)

        return redirect("projects:communication_detail", pk=root.pk)


@login_required
@require_POST
def set_active_organization(request, organization_id):
    membership = get_user_membership(request)
    if not membership:
        return redirect("accounts:login")
    try:
        set_active_context(request, organization_id=int(organization_id))
    except PermissionDenied:
        raise
    return redirect(request.META.get("HTTP_REFERER", "/"))
