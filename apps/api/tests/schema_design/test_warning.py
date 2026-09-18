from src.schema_design.domain.warning import SchemaWarning, WarningCode


def test_warning_codes_match_api_contract():
    assert WarningCode.MISSING_PRIMARY_KEY.value == "missing_primary_key"
    assert WarningCode.NON_ATOMIC_COLUMN_TYPE.value == "non_atomic_column_type"
    assert WarningCode.NULLABLE_FOREIGN_KEY.value == "nullable_foreign_key"
    assert WarningCode.NON_SNAKE_CASE_IDENTIFIER.value == "non_snake_case_identifier"


def test_warning_holds_all_fields():
    warning = SchemaWarning(
        code=WarningCode.MISSING_PRIMARY_KEY,
        table="logs",
        message="Table 'logs' has no primary key.",
    )

    assert warning.code == WarningCode.MISSING_PRIMARY_KEY
    assert warning.table == "logs"
