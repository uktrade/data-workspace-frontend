from dataworkspace.apps.datasets.templatetags.datasets_tags import format_table_name


class TestFormatTableName:
    def test_should_correctly_format_table_name(self):
        test_cases = [
            "This_Is_A_Table_Name",
            "this_is_a_table_name",
            "THIS_IS_A_TABLE_NAME",
            "tHIS_iS_a_tABLE_nAME",
            "This_is_a_table_name",
        ]

        for test in test_cases:
            assert format_table_name(test) == "This is a table name"
