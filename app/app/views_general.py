from django.http import HttpResponseRedirect
from django.urls import reverse
from django.views.generic import FormView

from app.forms import SupportForm
from app.zendesk import create_support_request


class SupportView(FormView):
    form_class = SupportForm
    template_name = 'app/support.html'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data()
        ctx['ticket_id'] = self.kwargs.get('ticket_id')
        return ctx

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'email': self.request.user.email,
        }
        return kwargs

    def form_valid(self, form):
        ticket_id = create_support_request(
            self.request.user,
            form.cleaned_data['email'],
            form.cleaned_data['message']
        )
        return HttpResponseRedirect(
            reverse('support-success', kwargs={'ticket_id': ticket_id})
        )
