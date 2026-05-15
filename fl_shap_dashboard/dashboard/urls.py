from django.urls import path
from . import views

urlpatterns = [
    path('',                     views.overview,       name='overview'),
    path('simulation/',          views.simulation,     name='simulation'),
    path('rounds/',              views.rounds,         name='rounds'),
    path('factories/',           views.factories,      name='factories'),
    path('factories/<int:factory_id>/', views.factory_detail, name='factory_detail'),
    path('explainability/',      views.explainability, name='explainability'),
    path('topology/',            views.topology,       name='topology'),
    path('monitor/',             views.monitor,        name='monitor'),
    path('api/monitor/',         views.monitor_api,    name='monitor_api'),
]