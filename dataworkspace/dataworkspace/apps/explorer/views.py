import logging

from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views import View
from waffle import flag_is_active

from dataworkspace.utils import DATA_EXPLORER_FLAG

logger = logging.getLogger('app')


class ExplorerIndex(View):
    def get(self, request, *args, **kwargs):
        if not flag_is_active(request, DATA_EXPLORER_FLAG):
            return HttpResponseForbidden()

        return render(request, 'explorer/index.html')
