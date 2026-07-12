{% macro candidate_location_matches(
    job_location,
    job_location_normalized,
    job_location_group,
    job_work_arrangement,
    configured_location
) %}
    (
        strpos(
            lower(coalesce({{ job_location }}, '')),
            lower({{ configured_location }})
        ) > 0
        or strpos(
            lower(coalesce({{ job_location_normalized }}, '')),
            lower({{ configured_location }})
        ) > 0
        or (
            lower({{ configured_location }}) = 'remote'
            and (
                lower(coalesce({{ job_work_arrangement }}, '')) = 'remote'
                or lower(coalesce({{ job_location_group }}, '')) = 'remote'
            )
        )
        or (
            strpos({{ configured_location }}, ',') > 0
            and length(trim(split_part({{ configured_location }}, ',', 1))) >= 3
            and (
                strpos(
                    lower(coalesce({{ job_location }}, '')),
                    lower(trim(split_part({{ configured_location }}, ',', 1)))
                ) > 0
                or strpos(
                    lower(coalesce({{ job_location_normalized }}, '')),
                    lower(trim(split_part({{ configured_location }}, ',', 1)))
                ) > 0
            )
        )
    )
{% endmacro %}
