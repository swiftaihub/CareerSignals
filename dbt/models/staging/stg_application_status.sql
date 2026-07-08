select
    user_id,
    job_id,
    application_status,
    notes,
    updated_at
from {{ source('app', 'job_application_status') }}
where job_id is not null
