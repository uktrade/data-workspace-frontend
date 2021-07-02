import json
from datetime import datetime

from csp.decorators import csp_update
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import DeleteView, ListView, RedirectView
from waffle.mixins import WaffleFlagMixin

from dataworkspace import datasets_db
from dataworkspace.apps.datasets.templatetags.datasets_tags import date_with_gmt_offset
from dataworkspace.apps.explorer.constants import QueryLogState
from dataworkspace.apps.explorer.models import ChartBuilderChart, QueryLog
from dataworkspace.apps.explorer.tasks import refresh_chart_thumbnail, run_chart_builder_query


class ChartCreateView(WaffleFlagMixin, RedirectView):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG

    def get_redirect_url(self, *args, **kwargs):
        # Given a data explorer query log we need to save the results
        # of the full query to a database table to allow us to query
        # it directly from the chart builder ui.
        original_query_log = get_object_or_404(
            QueryLog, pk=kwargs["query_log_id"], run_by_user=self.request.user
        )
        query_log = QueryLog.objects.create(
            sql=original_query_log.sql,
            query_id=original_query_log.query_id,
            run_by_user=self.request.user,
            connection=original_query_log.connection,
            page=1,
            page_size=None,
        )
        title = f"New chart ({date_with_gmt_offset(datetime.now())})"
        chart = ChartBuilderChart.objects.create(
            title=title,
            created_by=self.request.user,
            query_log=query_log,
            chart_config={"layout": {"title": {"text": title}}},
        )
        run_chart_builder_query.delay(chart.id)
        return chart.get_edit_url() + f"?ql={original_query_log.id}"


class ChartEditView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG
    template_name = "explorer/charts/chart_builder.html"

    @csp_update(SCRIPT_SRC=["'unsafe-eval'", "blob:"])
    def get(self, request, chart_id):
        chart = get_object_or_404(ChartBuilderChart, created_by=request.user, pk=chart_id)
        return render(
            request,
            self.template_name,
            context={
                "chart": chart,
                "back_link": reverse("explorer:running_query", args=(request.GET.get("ql"),))
                if "ql" in request.GET
                else reverse("explorer:explorer-charts:list-charts"),
            },
        )

    def post(self, request, chart_id):
        chart = get_object_or_404(ChartBuilderChart, created_by=request.user, pk=chart_id)
        chart.chart_config = json.loads(request.body).get("config", None)
        try:
            chart.title = chart.chart_config["layout"]["title"]["text"]
        except KeyError:
            pass
        chart.save()
        refresh_chart_thumbnail.delay(chart_id)
        return JsonResponse({}, status=200)


class ChartQueryStatusView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG

    def get(self, request, chart_id):
        try:
            chart = ChartBuilderChart.objects.get(created_by=request.user, pk=chart_id)
        except ChartBuilderChart.DoesNotExist:
            return JsonResponse(
                {"state": QueryLogState.FAILED, "error": "Query does not exist"}, status=404
            )

        return JsonResponse(
            {
                "state": chart.query_log.state,
                "error": chart.query_log.error,
                "columns": datasets_db.get_columns(
                    chart.query_log.connection, query=str(chart.query_log.sql)
                )
                if chart.query_log.state == QueryLogState.COMPLETE
                else [],
            }
        )


class ChartQueryResultsView(WaffleFlagMixin, View):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG

    def get(self, request, chart_id):
        chart = get_object_or_404(ChartBuilderChart, created_by=request.user, pk=chart_id)
        return JsonResponse(
            {
                "total_rows": chart.query_log.rows,
                "duration": chart.query_log.duration,
                "data": chart.get_table_data(),
            }
        )


class ChartListView(WaffleFlagMixin, ListView):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG
    model = QueryLog
    context_object_name = "charts"
    template_name = "explorer/charts/chartbuilderchart_list.html"

    def get_queryset(self):
        return ChartBuilderChart.objects.filter(created_by=self.request.user)


class ChartDeleteView(WaffleFlagMixin, DeleteView):
    waffle_flag = settings.CHART_BUILDER_BUILD_CHARTS_FLAG
    model = QueryLog
    success_url = reverse_lazy("explorer:explorer-charts:list-charts")
    pk_url_kwarg = "chart_id"
    template_name = "explorer/charts/chartbuilderchart_confirm_delete.html"

    def get_queryset(self):
        return ChartBuilderChart.objects.filter(created_by=self.request.user)

    def delete(self, request, *args, **kwargs):
        chart = self.get_object()
        if chart.is_published():
            return HttpResponseRedirect(chart.get_edit_url())
        return super().delete(request, *args, **kwargs)
