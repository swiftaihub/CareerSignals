-- Add the bootstrap waiting state before later migrations use it in DDL.

alter type public.pipeline_status add value if not exists 'waiting_for_global';
