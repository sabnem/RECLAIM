from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('report/', views.report_item, name='report_item'),
    path('items/', views.item_list, name='item_list'),
    path('items/<int:item_id>/', views.item_detail, name='item_detail'),
    path('items/<int:item_id>/contact/', views.contact_item_owner, name='contact_item_owner'),
    path('inbox/', views.inbox, name='inbox'),
    path('items/<int:item_id>/message/<int:recipient_id>/', views.send_message, name='send_message'),
]
