\c datasets;

-- Save and drop dependencies
create or replace function dataflow.save_and_drop_dependencies(p_view_schema character varying, p_view_name character varying) returns void as
$$
begin
end;
$$
LANGUAGE plpgsql;

alter function dataflow.save_and_drop_dependencies(varchar, varchar) owner to postgres;

-- Restore Dependencies
create or replace function dataflow.restore_dependencies(p_view_schema character varying, p_view_name character varying) returns void
    language plpgsql
as
$$
begin
end;
$$;

alter function dataflow.restore_dependencies(varchar, varchar) owner to postgres;
