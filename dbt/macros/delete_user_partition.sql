{% macro delete_user_partition() %}
    {% do require_user_context() %}
    {% if is_incremental() %}
        {% set column_names = adapter.get_columns_in_relation(this) | map(attribute='name') | map('lower') | list %}
        {% if 'user_uuid' in column_names and 'run_uuid' in column_names %}
            delete from {{ this }}
            where user_uuid = '{{ var("user_uuid") }}'
              and run_uuid = '{{ var("run_uuid") }}'
        {% else %}
            select 1 as noop where false
        {% endif %}
    {% else %}
        select 1 as noop where false
    {% endif %}
{% endmacro %}

{% macro purge_unscoped_user_rows() %}
    delete from {{ this }}
    where user_uuid is null or run_uuid is null
{% endmacro %}

{% macro purge_unscoped_shared_rows() %}
    delete from {{ this }}
    where connector_run_uuid is null
{% endmacro %}
