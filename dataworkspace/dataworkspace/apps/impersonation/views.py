from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.urls import reverse


def impersonate(request, user_id):
    user = get_user_model().objects.get(id=user_id)
    request.session['impersonated_user'] = user
    return HttpResponseRedirect(reverse('root'))


def stop_impersonating(request):
    del request.session['impersonated_user']
    return HttpResponseRedirect(reverse('root'))
