import pytest
from bs4 import BeautifulSoup
from django import forms
from django.template import Context, Template

from dataworkspace.apps.datasets.forms import FilterWidget


class TestFilterWidget:
    @pytest.mark.parametrize(
        "num_choices, limit_options, expect_show_more_button, expect_hidden_choices",
        (
            (5, 0, False, 0),
            (5, 2, True, 3),
            (5, 5, False, 0),
            (5, 10, False, 0),
        ),
    )
    def test_limit_initial_choices(
        self, num_choices, limit_options, expect_show_more_button, expect_hidden_choices
    ):
        class _Form(forms.Form):
            field = forms.MultipleChoiceField(
                choices=list((i, i) for i in range(num_choices)),
                required=False,
                widget=FilterWidget(
                    "Field",
                    limit_initial_options=limit_options,
                    show_more_label="Show more choices",
                ),
            )

        html = Template("{{ form }}").render(Context({"form": _Form()}))
        soup = BeautifulSoup(html)

        assert (
            len(soup.find_all("div", class_="govuk-checkboxes__item")) == num_choices
        ), "Widget should renderall of the choices"
        assert (
            bool(soup.find_all("button", text="Show more choices")) is expect_show_more_button
        ), "Widget should render a 'show more' button if there are more choices than we want to initially show."
        assert (
            len(soup.find_all("div", class_="govuk-checkboxes__item app-js-hidden"))
            == expect_hidden_choices
        ), "Widget should render excess options as hidden."
