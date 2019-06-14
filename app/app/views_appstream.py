import logging
import boto3
import gevent

from django.contrib import (
    messages,
)
from django.contrib.auth import (
    get_user_model,
)
from django.conf import (
    settings,
)
from django.http import (
    HttpResponse,
    HttpResponseNotAllowed,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
    StreamingHttpResponse,
)
from django.shortcuts import (
    redirect,
    render,
)

from .forms import AppstreamAdminForm

from app.models import (
    ApplicationInstance,
    ApplicationTemplate,
)
from app.shared import (
    database_dsn,
    get_private_privilages,
    new_private_database_credentials,
)
from app.appstream import (
    get_fleet_status,
    get_app_sessions,
    scale_fleet,
    get_fleet_scale,
    check_fleet_running,
    restart_fleet,
)


logger = logging.getLogger('app')


def appstream_view(request):
    User = get_user_model()
    fleet_status = get_fleet_status()

    for item in fleet_status['Fleets']:
        ComputeCapacityStatus = item['ComputeCapacityStatus']

    app_sessions = get_app_sessions()

    app_sessions_users = [
        (app_session, User.objects.get(profile__sso_id=app_session['UserId']))
        for app_session in app_sessions['Sessions']
    ]

    min_capacity, max_capacity = get_fleet_scale()

    context = {
        'fleet_status': ComputeCapacityStatus,
        'min_capacity': min_capacity,
        'max_capacity': max_capacity,
        'app_sessions_users': app_sessions_users,
    }

    return render(request, 'appstream.html', context)


def appstream_admin_view(request):
    fleet_status = check_fleet_running()

    if request.method == 'POST':
        form = AppstreamAdminForm(request.POST)

        if 'submit' in request.POST:
            if form.is_valid():
                new_min_capacity = int(form.cleaned_data['new_min_capacity'])
                new_max_capacity = int(form.cleaned_data['new_max_capacity'])
                print(new_min_capacity, new_max_capacity)
                scale_fleet(new_min_capacity, new_max_capacity)
                messages.success(request, 'New scaling values submitted')

                return redirect('appstream_admin')

        elif 'restart' in request.POST:
            print('Retarting cluster')
            messages.success(request, 'Restarting fleet')

            gevent.spawn(restart_fleet)

            return redirect('appstream_admin')
    else:
        form = AppstreamAdminForm()

    context = {
        'fleet_status': fleet_status,
        'form': form,
    }

    return render(request, 'appstream_admin.html', context)

def appstream_restart(request):
    fleet_status = check_fleet_running()

    if request.method == 'POST':
        if fleet_status == 'RUNNING':
            form = AppstreamAdminForm(request.POST)

            print('Retarting cluster')
            messages.success(request, 'Restarting fleet')

            gevent.spawn(restart_fleet)
        else:
            messages.success(request, 'Fleet is already in process of restarting')

        return redirect('appstream_admin')
    else:
        form = AppstreamAdminForm()

    context = {
        'fleet_status': fleet_status,
        'form': form,
    }

    return render(request, 'appstream_admin.html', context)

def appstream_fleetstatus(request):
    fleet_status = check_fleet_running()

    return HttpResponse(fleet_status)
