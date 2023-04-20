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
		-- From built-in Gamma role
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'AlertModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'DashboardEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'DruidColumnInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'DruidDatasourceModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'DruidMetricInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add', 'SliceEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_add_slices', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_annotation_json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_available_domains', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_copy_dash', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_created_dashboards', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_created_slices', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_csrf_token', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_csv', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_dashboard', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_dashboard_permalink', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_datasources', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete_embedded', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'AlertModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'DashboardEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'DruidColumnInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'DruidDatasourceModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'DruidMetricInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'SliceEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'TagView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'AlertModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'DashboardEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'DruidColumnInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'DruidDatasourceModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'DruidMetricInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_edit', 'SliceEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_estimate_query_cost', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_explore_json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_explore', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'Chart'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_external_metadata_by_name', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_external_metadata', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_extra_table_metadata', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_fave_dashboards_by_username', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_fave_dashboards', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_fave_slices', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_favstar', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_fetch_datasource_metadata', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_filter', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get embedded', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'Datasource'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'MenuApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'OpenApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get', 'TagView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get_value', 'KV'),
		(nextval('ab_permission_view_role_id_seq'), 'can_import_dashboards', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_invalidate', 'CacheRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'AlertLogModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'AlertModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'AlertObservationModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'AsyncEventsRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DashboardEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DruidClusterModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DruidColumnInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DruidDatasourceModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DruidMetricInlineView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'FilterSets'),
		(nextval('ab_permission_view_role_id_seq'), 'can_list', 'SliceEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_log', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_post', 'TagView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_profile', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_publish', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_queries', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_query_form_data', 'Api'),
		(nextval('ab_permission_view_role_id_seq'), 'can_query', 'Api'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'AdvancedDataType'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Annotation'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'AvailableDomains'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Chart'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'CssTemplate'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'DashboardFilterStateRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'DashboardPermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Database'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Dataset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'EmbeddedDashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'Explore'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'ExploreFormDataRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'ExplorePermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_read', 'SecurityRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_recent_activity', 'Log'),
		(nextval('ab_permission_view_role_id_seq'), 'can_recent_activity', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_refresh_datasources', 'Druid'),
		(nextval('ab_permission_view_role_id_seq'), 'can_request_access', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_results', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_save_dash', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_scan_new_datasources', 'Druid'),
		(nextval('ab_permission_view_role_id_seq'), 'can_schemas_access_for_csv_upload', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_schemas_access_for_file_upload', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_schemas', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_select_star', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_share_chart', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_share_dashboard', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_shortner', 'R'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'AlertLogModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'AlertModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'AlertObservationModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'DashboardEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'DruidClusterModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'DruidDatasourceModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'DynamicPlugin'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'SliceEmailScheduleView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_show', 'SwaggerView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_slice json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_slice', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_store', 'KV'),
		(nextval('ab_permission_view_role_id_seq'), 'can_suggestions', 'TagView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_tables', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_tagged_objects', 'TagView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_testconn', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_get', 'ResetMyPasswordView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_this_form_post', 'ResetMyPasswordView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_time_range', 'Api'),
		(nextval('ab_permission_view_role_id_seq'), 'can_user_slices', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_userinfo', 'UserRemoteUserModelView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Chart'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Dashboard'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'DashboardFilterStateRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'DashboardPermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'ExploreFormDataRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'ExplorePermalinkRestApi'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Access requests'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Alerts'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Chart Emails'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Charts'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Dashboard Email Schedules'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Dashboards'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Data'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Databases'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Datasets'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Druid Clusters'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Druid Datasources'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Home'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Import Dashboards'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Plugins'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Scan New Datasources'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'Upload a Columnar file'),
		(nextval('ab_permission_view_role_id_seq'), 'yaml_export', 'DruidDatasourceModelView'),

		-- Deliberately removed from built-in Gamma role
		-- Superset tries to validate SQL using "ecpg" which isn't installed, and if this
		-- permission is added, results in Access Denied shown to the user. Couldn't figure out
		-- how to install it, so leaving it for now
		-- (nextval('ab_permission_view_role_id_seq'), 'can_validate_sql_json', 'Supsetset'),

		-- From build-in sql_lab role
		-- The permissions do seem to be inconsistent with respect to case and spacing
		(nextval('ab_permission_view_role_id_seq'), 'can_activate', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_delete_query', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_execute_sql_query', 'SQLLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_export_csv', 'SQLLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_get_results', 'SQLLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_migrate_query', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_my_queries', 'SqlLab'),
		(nextval('ab_permission_view_role_id_seq'), 'can_post', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_put', 'TabStateView'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sql_json', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab_history', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab_table_viz', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'can_sqllab_viz', 'Superset'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'SQL Editor'),
		(nextval('ab_permission_view_role_id_seq'), 'menu_access', 'SQL Lab'),
		(nextval('ab_permission_view_role_id_seq'), 'stop_query', 'Superset'),

		-- Without this, get 405 errors when the front end POSTs to the log
		(nextval('ab_permission_view_role_id_seq'), 'can_write', 'Log')
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
