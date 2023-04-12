BEGIN;

-- Ensure Editor role exists
INSERT INTO ab_role(id, name) VALUES (nextval('ab_role_id_seq'), 'Editor') ON CONFLICT DO NOTHING;

-- Delete any existing editor permissions
DELETE FROM ab_permission_view_role WHERE role_id = (
	SELECT id FROM ab_role WHERE name = 'Editor'
);

-- Create set of editor permissions
-- Since the id column is not serial/autoincrement, we call nextval on a sequence explicitly
WITH required_permissions(new_permission_view_role_id, permission_name, view_menu_name) AS (
	VALUES
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'AdvancedDataType'),
		(nextval('ab_permission_view_role_id_seq'), 'all_database_access', 'all_database_access'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Annotation'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Annotation'),
		(nextval('ab_permission_view_role_id_seq'), 'can_query', 'Api'),
		(nextval('ab_permission_view_role_id_seq'), 'can_query_form_data', 'Api'),
		(nextval('ab_permission_view_role_id_seq'), 'can_time_range', 'Api'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'AsyncEventsRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'AvailableDomains'),
		(nextval('ab_permission_view_role_id_seq'), 'can_invalidate', 'CacheRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'Chart'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Chart'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Chart'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_get', 'ColumnarToDatabaseView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_post', 'ColumnarToDatabaseView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'CssTemplate'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'CssTemplate'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_get', 'CsvToDatabaseView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_post', 'CsvToDatabaseView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete_embedded', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get_embedded', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_set_embedded', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'DashboardFilterStateRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'DashboardFilterStateRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'DashboardPermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'DashboardPermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'Database'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Database'),
		(nextval('ab_permission_view_role_id_seq'), 'can_duplicate', 'Dataset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'Dataset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Dataset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Dataset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_external_metadata', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_external_metadata_by_name', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get_column_values', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_samples', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_save', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_download', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'EmbeddedDashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_get', 'ExcelToDatabaseView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_post', 'ExcelToDatabaseView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Explore'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'ExploreFormDataRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'ExploreFormDataRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'ExplorePermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'ExplorePermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'ImportExportRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_import_', 'ImportExportRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get_value', 'KV'),
		(nextval('ab_permission_view_role_id_seq'), 'can_store', 'KV'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Log'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'MenuApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'OpenApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Query'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'ReportSchedule'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'ReportSchedule'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_get', 'ResetMyPasswordView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_post', 'ResetMyPasswordView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_download', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'muldelete', 'RowLevelSecurityFiltersModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'SavedQuery'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'SavedQuery'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'SavedQuery'),
		(nextval('ab_permission_view_role_id_seq'), 'can_my_queries', 'SqlLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_execute_sql_query', 'SQLLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export_csv', 'SQLLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get_results', 'SQLLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add_slices', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_available_domains', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_copy_dash', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_created_dashboards', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_created_slices', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_dashboard', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_estimate_query_cost', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_explore_json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_fave_dashboards_by_username', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_favstar', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_fetch_datasource_metadata', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_override_role_permissions', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_profile', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_request_access', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_results', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_schemas_access_for_file_upload', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_slice', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sql_json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab_history', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab_viz', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_stop_query', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_validate_sql_json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'SwaggerView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_post', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_put', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'TagView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_get', 'UserInfoEditView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_post', 'UserInfoEditView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'UserRemoteUserModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'UserRemoteUserModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_recent_activity', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_recent_activity', 'Log'),
)

INSERT INTO ab_permission_view_role(id, permission_view_id, role_id)
	SELECT
		required_permissions.new_permission_view_role_id,
		ab_permission_view.id,
		ab_role.id
	FROM
		ab_permission_view
	INNER JOIN
		ab_permission ON
			ab_permission.id = ab_permission_view.permission_id
	INNER JOIN
		ab_view_menu ON
			ab_view_menu.id = ab_permission_view.view_menu_id
	INNER JOIN
		required_permissions ON
			required_permissions.permission_name = ab_permission.name
			AND required_permissions.view_menu_name = ab_view_menu.name
	INNER JOIN
		ab_role ON ab_role.name = 'Editor';

COMMIT;
