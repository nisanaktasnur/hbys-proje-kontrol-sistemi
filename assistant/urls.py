from django.urls import path

from assistant import views

app_name = "assistant"

urlpatterns = [
    path("yapay-zeka-asistani/", views.ChatView.as_view(), name="chat"),
    path("yapay-zeka-asistani/gonder/", views.send_message, name="send"),
    path("yapay-zeka-asistani/yeni/", views.new_conversation, name="new"),
    path("yapay-zeka-asistani/temizle/", views.clear_conversation, name="clear"),
]
