{% macro careersignal_clear_incremental_model() %}
    {% if is_incremental() %}
        delete from {{ this }}
    {% else %}
        select 1 as noop where false
    {% endif %}
{% endmacro %}
