from dataworkspace.apps.explorer.templatetags.explorer_tags import format_duration


def test_format_duration():

    assert (
        format_duration(36061001.3456) == '10 hours 1 minute 1 second 1.35 milliseconds'
    )
    assert format_duration(1) == '1 millisecond'
    assert format_duration(3600000) == '1 hour 0 minutes 0 seconds 0 milliseconds'
    assert format_duration(1000.2) == '1 second 0.2 milliseconds'
