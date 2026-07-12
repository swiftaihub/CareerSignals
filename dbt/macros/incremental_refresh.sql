{% macro careersignal_clear_incremental_model() %}
    {{ exceptions.raise_compiler_error(
        "Unqualified incremental clears are disabled; use delete_user_partition for user models"
    ) }}
{% endmacro %}
