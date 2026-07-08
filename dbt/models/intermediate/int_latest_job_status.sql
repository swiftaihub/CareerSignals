with ranked as (
    select
        *,
        row_number() over (
            partition by user_id, job_id
            order by updated_at desc
        ) as rn
    from {{ ref('stg_application_status') }}
)

select
    user_id,
    job_id,
    application_status,
    notes,
    updated_at
from ranked
where rn = 1
