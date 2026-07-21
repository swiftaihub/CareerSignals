{% macro require_user_context() %}
    {% set user_uuid = var('user_uuid', none) %}
    {% set run_uuid = var('run_uuid', none) %}
    {% set connector_run_uuid = var('connector_run_uuid', none) %}
    {% if execute and flags.WHICH in ['run', 'build', 'test'] and (user_uuid is none or run_uuid is none or connector_run_uuid is none or user_uuid | string | trim == '' or run_uuid | string | trim == '' or connector_run_uuid | string | trim == '') %}
        {{ exceptions.raise_compiler_error(
            "user_refresh requires non-empty user_uuid, run_uuid, and connector_run_uuid vars"
        ) }}
    {% endif %}
    {% if execute and flags.WHICH in ['run', 'build', 'test'] %}
        {% for field_name, raw_value in [('user_uuid', user_uuid), ('run_uuid', run_uuid), ('connector_run_uuid', connector_run_uuid)] %}
            {% set value = raw_value | string | trim | lower %}
            {% set compact = value | replace('-', '') %}
            {% set state = namespace(invalid=false) %}
            {% if value | length != 36 or value[8] != '-' or value[13] != '-' or value[18] != '-' or value[23] != '-' or compact | length != 32 %}
                {% set state.invalid = true %}
            {% endif %}
            {% for character in compact %}
                {% if character not in '0123456789abcdef' %}
                    {% set state.invalid = true %}
                {% endif %}
            {% endfor %}
            {% if state.invalid %}
                {{ exceptions.raise_compiler_error(
                    field_name ~ " must be a canonical UUID for user_refresh"
                ) }}
            {% endif %}
        {% endfor %}
    {% endif %}
{% endmacro %}

{% macro validate_shared_context() %}
    {% set raw_value = var('connector_run_uuid', none) %}
    {% if execute and raw_value is not none and raw_value | string | trim != '' %}
        {% set value = raw_value | string | trim | lower %}
        {% set compact = value | replace('-', '') %}
        {% set state = namespace(invalid=false) %}
        {% if value | length != 36 or value[8] != '-' or value[13] != '-' or value[18] != '-' or value[23] != '-' or compact | length != 32 %}
            {% set state.invalid = true %}
        {% endif %}
        {% for character in compact %}
            {% if character not in '0123456789abcdef' %}
                {% set state.invalid = true %}
            {% endif %}
        {% endfor %}
        {% if state.invalid %}
            {{ exceptions.raise_compiler_error(
                "connector_run_uuid must be a canonical UUID for shared_refresh"
            ) }}
        {% endif %}
    {% endif %}
{% endmacro %}
