# Personal Current State

Personal dbt models in the `user_refresh` selector are run-scoped publication inputs. They keep `user_uuid` and `run_uuid` in their grain so the worker can validate one immutable dbt output partition before publishing it.

The PostgreSQL serving tables are the user-visible current state:

| Table | Current-state grain | Lineage field |
| --- | --- | --- |
| `public.user_job_matches` | `user_uuid + job_id` where `is_current = true` | `run_uuid`, `first_created_run_uuid`, `last_updated_run_uuid`, `last_evaluated_run_uuid` |
| `public.user_category_summary` | `user_uuid + category_name` where `is_current = true` | same lineage columns |
| `public.user_skill_gap` | `user_uuid + canonical_skill` where `is_current = true` | same lineage columns |
| `public.user_company_priority` | `user_uuid + company_name` where `is_current = true` | same lineage columns |

A personal refresh is an incremental merge into those serving tables:

1. Read the run-scoped dbt output for the publishing `user_uuid` and `run_uuid`.
2. Clear only unpublished retry rows for that same user/run.
3. Mark current rows for touched business keys as historical.
4. Insert the new row versions as current.
5. Explicitly deactivate rows whose shared job is inactive.
6. Advance `user_profiles.last_successful_pipeline_run_uuid` only after the transaction succeeds.

Rows from previous successful runs remain visible when they still belong to the user and were not explicitly superseded or deactivated. User-facing APIs should query the authenticated user's current rows (`user_uuid` plus `is_current = true`), not `run_uuid = latest_successful_run_uuid`.
