-- PostgreSQL numeric accepts NaN and infinities. Treat those source artifacts
-- as missing salaries so aggregates remain meaningful and JSON-safe.

update public.job_postings
set
    salary_min = case
        when salary_min::text in ('NaN', 'Infinity', '-Infinity') then null
        else salary_min
    end,
    salary_max = case
        when salary_max::text in ('NaN', 'Infinity', '-Infinity') then null
        else salary_max
    end,
    updated_at = now()
where salary_min::text in ('NaN', 'Infinity', '-Infinity')
   or salary_max::text in ('NaN', 'Infinity', '-Infinity');

alter table public.job_postings
    add constraint job_postings_salary_min_finite_check check (
        salary_min is null
        or salary_min::text not in ('NaN', 'Infinity', '-Infinity')
    ),
    add constraint job_postings_salary_max_finite_check check (
        salary_max is null
        or salary_max::text not in ('NaN', 'Infinity', '-Infinity')
    );
