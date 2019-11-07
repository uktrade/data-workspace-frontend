from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from dataworkspace.apps.datasets.forms import RequestAccessForm, EligibilityCriteriaForm
from dataworkspace.apps.datasets.utils import find_dataset
from dataworkspace.zendesk import create_zendesk_ticket


@require_http_methods(['GET', 'POST'])
def eligibility_criteria_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    if request.method == 'POST':
        form = EligibilityCriteriaForm(request.POST)
        if form.is_valid():
            if form.cleaned_data['meet_criteria']:
                return HttpResponseRedirect(
                    reverse('datasets:request_access', args=[group_slug, set_slug])
                )
            else:
                return HttpResponseRedirect(
                    reverse(
                        'datasets:eligibility_criteria_not_met',
                        args=[group_slug, set_slug],
                    )
                )

    return render(request, 'eligibility_criteria.html', {'dataset': dataset})


@require_GET
def eligibility_criteria_not_met_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    return render(request, 'eligibility_criteria_not_met.html', {'dataset': dataset})


@require_http_methods(['GET', 'POST'])
def request_access_view(request, group_slug, set_slug):
    dataset = find_dataset(group_slug, set_slug)

    if request.method == 'POST':
        form = RequestAccessForm(request.POST)
        if form.is_valid():
            goal = form.cleaned_data['goal']
            justification = form.cleaned_data['justification']
            contact_email = form.cleaned_data['email']

            user_edit_relative = reverse(
                'admin:auth_user_change', args=[request.user.id]
            )
            user_url = request.build_absolute_uri(user_edit_relative)

            dataset_name = f'{dataset.grouping.name} > {dataset.name}'

            dataset_url = request.build_absolute_uri(
                reverse('catalogue:dataset_fullpath', args=[group_slug, set_slug])
            )

            ticket_reference = create_zendesk_ticket(
                contact_email,
                request.user,
                goal,
                justification,
                user_url,
                dataset_name,
                dataset_url,
                dataset.grouping.information_asset_owner,
                dataset.grouping.information_asset_manager,
            )

            url = reverse('datasets:request_access_success')
            return HttpResponseRedirect(
                f'{url}?ticket={ticket_reference}&group={group_slug}&set={set_slug}'
            )

    return render(
        request,
        'request_access.html',
        {'dataset': dataset, 'authenticated_user': request.user},
    )


@require_GET
def request_access_success_view(request):
    # yes this could cause 400 errors but Todo - replace with session / messages
    ticket = request.GET['ticket']
    group_slug = request.GET['group']
    set_slug = request.GET['set']

    dataset = find_dataset(group_slug, set_slug)

    return render(
        request, 'request_access_success.html', {'ticket': ticket, 'dataset': dataset}
    )
