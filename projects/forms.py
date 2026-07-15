from django import forms

from django.contrib.auth.models import User

from projects.models import (
    DecisionSource,
    DecisionSupportRecord,
    FeedbackSource,
    ImpactLevel,
    InstructionStatus,
    MetricCategory,
    MetricStatus,
    PostGoLiveMetric,
    Priority,
    ProcessArea,
    ProjectCommunication,
    ProjectRisk,
    ProjectRiskStatus,
    RequestRecord,
    RequestStatus,
    RiskCategory,
    RiskLevel,
    UATRecord,
    UATResultStatus,
)


def _apply_form_controls(form):
    for name, field in form.fields.items():
        if name != "has_workaround" and "class" not in field.widget.attrs:
            field.widget.attrs["class"] = "form-control"


def _set_choice_placeholder(field, label="Seçiniz"):
    if hasattr(field, "empty_label"):
        field.empty_label = label
    elif isinstance(field, forms.ChoiceField):
        choices = list(field.choices)
        if choices and choices[0][0] == "":
            field.choices = [("", label)] + choices[1:]
        else:
            field.choices = [("", label)] + choices


def _remove_empty_queryset_fields(form, field_names):
    """Boş seçenekli ModelChoiceField alanlarını formdan kaldır."""
    for name in list(field_names):
        field = form.fields.get(name)
        if not field:
            continue
        if hasattr(field, "queryset") and not field.queryset.exists():
            del form.fields[name]
        elif hasattr(field, "queryset"):
            _set_choice_placeholder(field)
            field.required = False


def _operational_role_choices():
    from accounts.models import Role

    return [("", "Seçiniz")] + [
        (value, label)
        for value, label in Role.choices
        if value != Role.SISTEM_YONETICISI
    ]


def _filter_org_users(field, organization):
    from django.contrib.auth.models import User

    field.empty_label = "Seçiniz"
    field.queryset = User.objects.filter(
        memberships__organization=organization,
        memberships__is_active=True,
        profile__approval_status="Onaylı",
    ).distinct()
    field.required = False


def _filter_project_users(field, project):
    from accounts.models import ApprovalStatus

    field.empty_label = "Seçiniz"
    field.queryset = User.objects.filter(
        project_memberships__project=project,
        project_memberships__is_active=True,
        profile__approval_status=ApprovalStatus.APPROVED,
    ).distinct()
    field.required = False


class RequestRecordForm(forms.ModelForm):
    class Meta:
        model = RequestRecord
        fields = [
            "title",
            "description",
            "feedback_source",
            "process_area",
            "priority",
            "status",
            "responsible_team",
            "owner",
            "due_date",
            "go_live_impact",
            "has_workaround",
            "affects_patient_or_user_safety",
            "operational_impact",
            "solution_note",
            "completed_at",
        ]
        labels = {
            "title": "Talep Başlığı",
            "description": "Açıklama",
            "feedback_source": "Geri Bildirim Kaynağı",
            "process_area": "İlgili Süreç",
            "priority": "Öncelik",
            "status": "Durum",
            "responsible_team": "Sorumlu Ekip",
            "owner": "Sorumlu Kullanıcı",
            "due_date": "Hedef Kapanış Tarihi",
            "go_live_impact": "Canlı Geçiş Etkisi",
            "has_workaround": "Geçici Çözüm Var mı?",
            "affects_patient_or_user_safety": "Kullanıcı/Hasta Güvenliği Etkisi",
            "operational_impact": "Operasyonel Etki",
            "solution_note": "Çözüm Notu",
            "completed_at": "Tamamlanma Tarihi",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
            "due_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "completed_at": forms.DateInput(attrs={"type": "datetime-local", "class": "form-control"}),
            "solution_note": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "has_workaround": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        if organization:
            _filter_org_users(self.fields["owner"], organization)
        for name in ("feedback_source", "process_area", "priority", "status", "go_live_impact", "affects_patient_or_user_safety", "operational_impact"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)
        for name in (
            "title",
            "description",
            "feedback_source",
            "process_area",
            "priority",
            "status",
            "responsible_team",
            "due_date",
            "go_live_impact",
            "operational_impact",
        ):
            if name in self.fields:
                self.fields[name].required = True

    def clean(self):
        cleaned = super().clean()
        priority = cleaned.get("priority")
        go_live = cleaned.get("go_live_impact")
        status = cleaned.get("status")
        safety = cleaned.get("affects_patient_or_user_safety")
        workaround = cleaned.get("has_workaround")
        due_date = cleaned.get("due_date")
        solution_note = cleaned.get("solution_note", "")

        if priority == Priority.YUKSEK:
            if not safety:
                self.add_error(
                    "affects_patient_or_user_safety",
                    "Yüksek öncelikli taleplerde güvenlik etkisi zorunludur.",
                )
            if workaround is None:
                self.add_error(
                    "has_workaround",
                    "Yüksek öncelikli taleplerde geçici çözüm bilgisi zorunludur.",
                )
        if go_live == ImpactLevel.YUKSEK:
            if workaround is None:
                self.add_error(
                    "has_workaround",
                    "Yüksek canlı geçiş etkisinde geçici çözüm bilgisi zorunludur.",
                )
            if not due_date:
                self.add_error(
                    "due_date",
                    "Yüksek canlı geçiş etkisinde hedef kapanış tarihi zorunludur.",
                )
        if status == RequestStatus.TAMAMLANDI:
            if not solution_note:
                self.add_error(
                    "solution_note",
                    "Tamamlanan taleplerde çözüm notu zorunludur.",
                )
            if not cleaned.get("completed_at"):
                self.add_error(
                    "completed_at",
                    "Tamamlanan taleplerde tamamlanma tarihi zorunludur.",
                )
        return cleaned


class RequestFilterForm(forms.Form):
    q = forms.CharField(label="Ara", required=False, widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Başlık veya ekip..."}))
    status = forms.ChoiceField(label="Durum", required=False, choices=[("", "Tümü")] + list(RequestStatus.choices), widget=forms.Select(attrs={"class": "form-control"}))
    risk_level = forms.ChoiceField(label="Risk Seviyesi", required=False, choices=[("", "Tümü"), ("Düşük", "Düşük"), ("Orta", "Orta"), ("Yüksek", "Yüksek")], widget=forms.Select(attrs={"class": "form-control"}))
    process_area = forms.ChoiceField(label="İlgili Süreç", required=False, choices=[("", "Tümü")] + list(ProcessArea.choices), widget=forms.Select(attrs={"class": "form-control"}))
    responsible_team = forms.CharField(label="Sorumlu Ekip", required=False, widget=forms.TextInput(attrs={"class": "form-control"}))
    owner = forms.ModelChoiceField(
        label="Sorumlu Kullanıcı",
        required=False,
        queryset=User.objects.none(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    overdue = forms.BooleanField(label="Yalnızca Geciken", required=False, widget=forms.CheckboxInput(attrs={"class": "form-check-input"}))
    sort = forms.ChoiceField(
        label="Sıralama",
        required=False,
        choices=[
            ("-updated_at", "Son Güncelleme (Yeni)"),
            ("updated_at", "Son Güncelleme (Eski)"),
            ("due_date", "Hedef Tarih (Yakın)"),
            ("-due_date", "Hedef Tarih (Uzak)"),
            ("title", "Başlık"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
    )

    def __init__(self, *args, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        if organization:
            from django.contrib.auth.models import User

            _filter_org_users(self.fields["owner"], organization)


class TechnicalRequestUpdateForm(forms.ModelForm):
    class Meta:
        model = RequestRecord
        fields = [
            "technical_owner",
            "technical_status",
            "has_workaround",
            "root_cause_status",
            "solution_note",
            "retest_status",
            "recommended_action",
            "evaluation_note",
        ]
        labels = {
            "technical_owner": "Teknik Sorumlu",
            "technical_status": "Teknik Durum",
            "has_workaround": "Geçici Çözüm Var mı?",
            "root_cause_status": "Kök Neden Durumu",
            "solution_note": "Çözüm Notu",
            "retest_status": "Tekrar Test Durumu",
            "recommended_action": "Önerilen Aksiyon",
            "evaluation_note": "Teknik Değerlendirme Notu",
        }
        widgets = {
            "solution_note": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "recommended_action": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "evaluation_note": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "has_workaround": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        if project:
            _filter_project_users(self.fields["technical_owner"], project)
        for name in ("technical_status", "root_cause_status", "retest_status"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)


class UATTechnicalUpdateForm(forms.ModelForm):
    class Meta:
        model = UATRecord
        fields = [
            "root_cause_note",
            "resolution_note",
            "retest_status",
            "result_status",
        ]
        labels = {
            "root_cause_note": "Kök Neden Notu",
            "resolution_note": "Teknik Çözüm Notu",
            "retest_status": "Tekrar Test Durumu",
            "result_status": "Sonuç Durumu",
        }
        widgets = {
            "root_cause_note": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
            "resolution_note": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        for name in ("result_status", "retest_status"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)


class DecisionSupportForm(forms.ModelForm):
    class Meta:
        model = DecisionSupportRecord
        fields = [
            "source",
            "title",
            "finding",
            "recommendation",
            "expected_effect",
            "priority",
            "owner",
            "responsible_team",
            "status",
            "due_date",
            "related_request",
            "related_project_risk",
            "related_uat_record",
            "related_post_go_live_metric",
            "notes",
        ]
        labels = {
            "source": "Kaynak",
            "title": "Başlık",
            "finding": "Tespit",
            "recommendation": "Önerilen Karar",
            "expected_effect": "Beklenen Etki",
            "priority": "Öncelik",
            "owner": "Sorumlu",
            "responsible_team": "Sorumlu Ekip",
            "status": "Durum",
            "due_date": "Hedef Tarih",
            "related_request": "İlgili Talep",
            "related_project_risk": "İlgili Proje Riski",
            "related_uat_record": "İlgili UAT Kaydı",
            "related_post_go_live_metric": "İlgili Canlı Geçiş Göstergesi",
            "notes": "Notlar",
        }

    def __init__(self, *args, project=None, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        if project:
            for name in ("related_request", "related_project_risk", "related_uat_record", "related_post_go_live_metric"):
                field = self.fields.get(name)
                if not field:
                    continue
                if name == "related_request":
                    field.queryset = RequestRecord.objects.filter(project=project)
                elif name == "related_project_risk":
                    field.queryset = ProjectRisk.objects.filter(project=project)
                elif name == "related_uat_record":
                    field.queryset = UATRecord.objects.filter(project=project)
                elif name == "related_post_go_live_metric":
                    field.queryset = PostGoLiveMetric.objects.filter(project=project)
                field.required = False
            _remove_empty_queryset_fields(
                self,
                [
                    "related_request",
                    "related_project_risk",
                    "related_uat_record",
                    "related_post_go_live_metric",
                ],
            )
        if organization:
            _filter_org_users(self.fields["owner"], organization)
            if not self.fields["owner"].queryset.exists():
                del self.fields["owner"]
        for name in ("source", "priority", "status"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)


class ProjectRiskForm(forms.ModelForm):
    class Meta:
        model = ProjectRisk
        fields = [
            "title",
            "description",
            "category",
            "probability",
            "impact",
            "mitigation_action",
            "contingency_action",
            "owner",
            "due_date",
            "status",
            "related_request",
        ]
        labels = {
            "title": "Risk Başlığı",
            "description": "Risk Açıklaması",
            "category": "Risk Kategorisi",
            "probability": "Olasılık",
            "impact": "Etki Seviyesi",
            "mitigation_action": "Önleyici Aksiyon",
            "contingency_action": "Gerçekleşme Durumunda Aksiyon",
            "owner": "Sorumlu",
            "due_date": "Hedef Tarih",
            "status": "Durum",
            "related_request": "İlgili Talep",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "mitigation_action": forms.Textarea(attrs={"rows": 2}),
            "contingency_action": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, project=None, organization=None, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        self.fields["risk_level"] = forms.CharField(
            label="Risk Seviyesi",
            required=False,
            widget=forms.TextInput(attrs={"class": "form-control", "readonly": "readonly"}),
        )
        if self.instance and self.instance.pk:
            self.fields["risk_level"].initial = self.instance.risk_level
        if project:
            _set_choice_placeholder(self.fields["related_request"])
            self.fields["related_request"].queryset = RequestRecord.objects.filter(project=project)
            _remove_empty_queryset_fields(self, ["related_request"])
        if organization:
            _filter_org_users(self.fields["owner"], organization)
            if not self.fields["owner"].queryset.exists():
                del self.fields["owner"]
        for name in ("category", "probability", "impact", "status"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)


class UATRecordForm(forms.ModelForm):
    class Meta:
        model = UATRecord
        fields = [
            "scenario_name",
            "process_area",
            "expected_result",
            "actual_result",
            "result_status",
            "severity",
            "responsible_team",
            "tester_name",
            "tester_role",
            "test_date",
            "resolution_note",
            "related_request",
        ]
        labels = {
            "scenario_name": "Senaryo Adı",
            "process_area": "İlgili Süreç",
            "expected_result": "Beklenen Sonuç",
            "actual_result": "Gerçekleşen Sonuç",
            "result_status": "Sonuç Durumu",
            "severity": "Önem Düzeyi",
            "responsible_team": "Sorumlu Ekip",
            "tester_name": "Test Eden",
            "tester_role": "Test Eden Rol",
            "test_date": "Test Tarihi",
            "resolution_note": "Çözüm Notu",
            "related_request": "İlgili Talep",
        }
        widgets = {
            "expected_result": forms.Textarea(attrs={"rows": 2}),
            "actual_result": forms.Textarea(attrs={"rows": 2}),
            "resolution_note": forms.Textarea(attrs={"rows": 2}),
            "test_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, project=None, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        if project:
            self.fields["related_request"].queryset = RequestRecord.objects.filter(project=project)
            self.fields["related_request"].required = False
            _remove_empty_queryset_fields(self, ["related_request"])
        for name in ("process_area", "result_status", "severity"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)


class PostGoLiveMetricForm(forms.ModelForm):
    class Meta:
        model = PostGoLiveMetric
        fields = [
            "metric_name",
            "metric_category",
            "target_value",
            "current_value",
            "unit",
            "status",
            "measurement_date",
            "responsible_team",
            "evaluation_note",
        ]
        labels = {
            "metric_name": "Gösterge Adı",
            "metric_category": "Gösterge Kategorisi",
            "target_value": "Hedef Değer",
            "current_value": "Güncel Değer",
            "unit": "Birim",
            "status": "Durum",
            "measurement_date": "Ölçüm Tarihi",
            "responsible_team": "Sorumlu Ekip",
            "evaluation_note": "Değerlendirme Notu",
        }
        widgets = {
            "evaluation_note": forms.Textarea(attrs={"rows": 2}),
            "measurement_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        for name in ("metric_category", "status"):
            field = self.fields.get(name)
            if field:
                _set_choice_placeholder(field)


class ExecutiveFilterForm(forms.Form):
    project = forms.ChoiceField(
        label="Proje",
        required=False,
        choices=[("", "Tümü")],
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    process_area = forms.ChoiceField(
        label="Süreç",
        required=False,
        choices=[("", "Tümü")] + list(ProcessArea.choices),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    responsible_team = forms.CharField(
        label="Sorumlu Ekip",
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control"}),
    )
    date_from = forms.DateField(
        label="Başlangıç",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        label="Bitiş",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )

    def __init__(self, *args, projects=None, **kwargs):
        super().__init__(*args, **kwargs)
        if projects is not None:
            choices = [("", "Tümü")] + [(str(p.id), p.name) for p in projects]
            self.fields["project"].choices = choices


class CommunicationForm(forms.ModelForm):
    class Meta:
        model = ProjectCommunication
        fields = [
            "communication_type",
            "title",
            "description",
            "recipient_role",
            "recipient_user",
            "related_request",
            "related_project_risk",
            "related_uat_record",
            "related_decision",
            "priority",
            "due_date",
        ]
        labels = {
            "communication_type": "Tür",
            "title": "Başlık",
            "description": "Açıklama",
            "recipient_role": "Alıcı Rol",
            "recipient_user": "Alıcı Kullanıcı",
            "related_request": "İlgili Talep",
            "related_project_risk": "İlgili Risk",
            "related_uat_record": "İlgili UAT",
            "related_decision": "İlgili Karar",
            "priority": "Öncelik",
            "due_date": "Hedef Tarih",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, project=None, organization=None, comm_type=None, **kwargs):
        from projects.models import CommunicationType

        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        comm_type = comm_type or (
            self.initial.get("communication_type") or CommunicationType.MESAJ
        )
        if comm_type == CommunicationType.MESAJ:
            self.fields.pop("priority", None)
            self.fields.pop("due_date", None)
        if project:
            _filter_project_users(self.fields["recipient_user"], project)
            if not self.fields["recipient_user"].queryset.exists():
                del self.fields["recipient_user"]
            self.fields["related_request"].queryset = RequestRecord.objects.filter(project=project)
            self.fields["related_project_risk"].queryset = ProjectRisk.objects.filter(project=project)
            self.fields["related_uat_record"].queryset = UATRecord.objects.filter(project=project)
            self.fields["related_decision"].queryset = DecisionSupportRecord.objects.filter(project=project)
            for name in (
                "related_request",
                "related_project_risk",
                "related_uat_record",
                "related_decision",
            ):
                if name in self.fields:
                    self.fields[name].required = False
            _remove_empty_queryset_fields(
                self,
                [
                    "related_request",
                    "related_project_risk",
                    "related_uat_record",
                    "related_decision",
                ],
            )
        else:
            for name in (
                "recipient_user",
                "related_request",
                "related_project_risk",
                "related_uat_record",
                "related_decision",
            ):
                self.fields.pop(name, None)
        self.fields["recipient_role"].choices = _operational_role_choices()
        self.fields["recipient_role"].required = False
        if comm_type == CommunicationType.TALIMAT:
            priority = self.fields.get("priority")
            if priority:
                _set_choice_placeholder(priority)
        if "communication_type" in self.fields:
            self.fields["communication_type"].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        recipient_role = cleaned_data.get("recipient_role")
        recipient_user = cleaned_data.get("recipient_user")
        if not recipient_role and not recipient_user:
            raise forms.ValidationError("Alıcı rol veya alıcı kullanıcı seçilmelidir.")
        return cleaned_data


class CommunicationStatusForm(forms.ModelForm):
    class Meta:
        model = ProjectCommunication
        fields = ["status", "completion_note"]
        labels = {
            "status": "Talimat Durumu",
            "completion_note": "Tamamlanma Notu",
        }
        widgets = {
            "completion_note": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _apply_form_controls(self)
        _set_choice_placeholder(self.fields["status"])

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        completion_note = cleaned_data.get("completion_note")
        if status == InstructionStatus.TAMAMLANDI and not (completion_note or "").strip():
            self.add_error("completion_note", "Tamamlanma notu girilmelidir.")
        return cleaned_data


class CommunicationReplyForm(forms.Form):
    description = forms.CharField(
        label="Yanıt Metni",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )

    def clean_description(self):
        value = (self.cleaned_data.get("description") or "").strip()
        if not value:
            raise forms.ValidationError("Yanıt metni boş olamaz.")
        return value

