from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.urls import reverse


def impersonate(request, id):
    user = get_user_model().objects.get(id=id)
    request.session['impersonated_user'] = user
    return HttpResponseRedirect(reverse('root'))
