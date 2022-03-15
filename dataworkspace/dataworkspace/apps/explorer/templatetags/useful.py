from django import template

register = template.Library()

HOME_MENU_ITEM = "home"
QUERY_LIST_ITEM = "queries"
LOGS_MENU_ITEM = "logs"
CHARTS_MENU_ITEM = "charts"


@register.simple_tag(takes_context=True)
def get_active_menu(context):  # pylint: disable=inconsistent-return-statements
    view_name = context["request"].resolver_match.url_name
    if view_name in {"index"}:
        return HOME_MENU_ITEM
    if view_name == "explorer_logs":
        return LOGS_MENU_ITEM
    if view_name in {"list_queries", "query_detail"}:
        return QUERY_LIST_ITEM
    if view_name in {"list-charts"}:
        return CHARTS_MENU_ITEM
