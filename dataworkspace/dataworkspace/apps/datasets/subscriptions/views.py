import logging

from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View
from django.views.generic import UpdateView

from dataworkspace.apps.datasets.models import DataSet, DataSetSubscription, ReferenceDataset
from dataworkspace.apps.datasets.subscriptions.forms import (
    DataSetSubscriptionForm,
    NotificationType,
)
from dataworkspace.apps.datasets.subscriptions.utils import (
    subscribe,
    unsubscribe_from_all,
    unsubscribe,
)
from dataworkspace.apps.eventlog.models import EventLog
from dataworkspace.apps.eventlog.utils import log_event

logger = logging.getLogger("app")


def current_user_email_preferences_list(request):
    user = request.user

    subscriptions = DataSetSubscription.objects.active(user=user)

    return render(
        request,
        "datasets/subscriptions/user_email_preferences.html",
        context={"subscriptions": subscriptions},
    )


class DataSetSubscriptionUnsubscribe(View):
    def get(self, request, subscription_id):
        # We overload the subscription_id to allow us to use the same route
        # for unsubscribe all. If subscription_id == __all__ this means unsubscribe all.

        if subscription_id == "__all__":
            subscriptions = DataSetSubscription.objects.filter(user=request.user).order_by(
                "dataset__name"
            )
        else:
            subscription = get_object_or_404(DataSetSubscription, pk=subscription_id)
            if request.user.id != subscription.user.id:
                # This is really a 403, but we don't want to leak information
                raise Http404()

            subscriptions = [subscription]

        return render(
            request,
            "datasets/subscriptions/unsubscribe_review.html",
            context={
                "subscriptions": [s for s in subscriptions if s.is_active()],
                "question_text": "Are you sure you want to unsubscribe?",
            },
        )

    def post(self, request, subscription_id):
        if subscription_id == "__all__":
            # Ignore the post values and just delete all subscriptions
            unsubscribed = unsubscribe_from_all(request.user)
        else:
            unsubscribed = [unsubscribe(subscription_id, request.user)]

        for subscription in unsubscribed:
            log_event(
                request.user,
                EventLog.TYPE_DATASET_NOTIFICATIONS_UNSUBSCRIBED,
                related_object=subscription,
            )

        return render(
            request,
            "datasets/subscriptions/unsubscribe_confirm.html",
            context={"subscriptions": unsubscribed},
        )


class DataSetSubscriptionStartView(View):
    def get(self, request, dataset_uuid):
        try:
            dataset = ReferenceDataset.objects.live().get(uuid=dataset_uuid)
        except ReferenceDataset.DoesNotExist:
            dataset = get_object_or_404(DataSet, id=dataset_uuid)

        subscription = subscribe(user=request.user, dataset=dataset)
        return render(
            request,
            "datasets/subscriptions/step_1_start.html",
            context={"dataset": dataset, "subscription": subscription},
        )


class DataSetSubscriptionView(UpdateView):
    template_name = "datasets/subscriptions/step_2_options.html"
    form_class = DataSetSubscriptionForm
    model = DataSetSubscription

    def form_valid(self, form):
        if form.cleaned_data["notification_type"] == NotificationType.COLUMNS:
            form.instance.notify_on_schema_change = True
            form.instance.notify_on_data_change = False
        elif form.cleaned_data["notification_type"] == NotificationType.ALL_CHANGES:
            form.instance.notify_on_schema_change = True
            form.instance.notify_on_data_change = True
        log_event(
            self.request.user,
            EventLog.TYPE_DATASET_NOTIFICATIONS_SUBSCRIBED,
            related_object=form.instance,
            extra={
                "notify_on_schema_change": form.instance.notify_on_schema_change,
                "notify_on_data_change": form.instance.notify_on_data_change,
            },
        )
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("datasets:subscription_review", args=[self.object.id])


class DataSetSubscriptionReview(UpdateView):
    template_name = "datasets/subscriptions/step_3_review.html"
    model = DataSetSubscription
    fields = []

    def get_success_url(self):
        return reverse("datasets:subscription_confirm", args=[self.object.id])


class DataSetSubscriptionConfirm(View):
    def get(self, request, subscription_id):
        subscription = get_object_or_404(DataSetSubscription, id=subscription_id)

        return render(
            request,
            "datasets/subscriptions/step_4_confirm.html",
            context={"dataset": subscription.dataset, "subscription": subscription},
        )
