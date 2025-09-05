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
    path('items/<int:item_id>/mark_returned/', views.mark_item_returned, name='mark_item_returned'),
    path('inbox/', views.inbox, name='inbox'),
    path('items/<int:item_id>/message/<int:recipient_id>/', views.send_message, name='send_message'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path("remove-profile-picture/", views.remove_profile_picture, name="remove_profile_picture"),
    path('delete-account/', views.delete_account, name='delete_account'),
    path('items/<int:item_id>/return_confirmation/', views.return_confirmation, name='return_confirmation'),
    path('review/<int:user_id>/', views.submit_review, name='submit_review'),
]
