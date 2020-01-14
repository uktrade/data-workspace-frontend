external_url 'https://${external_domain}'
nginx['listen_port'] = 80
nginx['listen_https'] = false
letsencrypt['enable'] = false
redis['enable'] = false
postgresql['enable'] = false
gitlab_rails['redis_host'] = '${redis__host}'
gitlab_rails['redis_port'] = ${redis__port}
gitlab_rails['db_adapter'] = 'postgresql'
gitlab_rails['db_encoding'] = 'utf8'
gitlab_rails['db_host'] = '${db__host}'
gitlab_rails['db_port'] = ${db__port}
gitlab_rails['db_username'] = '${db__user}'
gitlab_rails['db_password'] = '${db__password}'
gitlab_rails['db_database'] = '${db__name}'
gitlab_rails['uploads_object_store_enabled'] = true
gitlab_rails['uploads_object_store_remote_directory'] = 'uploads'
gitlab_rails['uploads_object_store_connection'] = {
  'provider' => 'AWS',
  'region' => '${bucket__region}',
  'host' => '${bucket__domain}',
  'use_iam_profile' => true
}
gitlab_rails['artifacts_enabled'] = true
gitlab_rails['artifacts_object_store_enabled'] = true;
gitlab_rails['artifacts_object_store_remote_directory'] = 'artifacts';
gitlab_rails['artifacts_object_store_connection'] = {
  'provider' => 'AWS',
  'region' => '${bucket__region}',
  'host' => '${bucket__domain}',
  'use_iam_profile' => true
}
gitlab_rails['lfs_object_store_enabled'] = true
gitlab_rails['lfs_object_store_remote_directory'] = 'lfs-objects'
gitlab_rails['lfs_object_store_connection'] = {
  'provider' => 'AWS',
  'region' => 'eu-west-2',
  'host' => '${bucket__domain}',
  'use_iam_profile' => true
}
gitlab_rails['external_diffs_enabled'] = true
gitlab_rails['external_diffs_object_store_enabled'] = true
gitlab_rails['external_diffs_object_store_remote_directory'] = 'external-diffs'
gitlab_rails['external_diffs_object_store_connection'] = {
  'provider' => 'AWS',
  'region' => '${bucket__region}',
  'host' => '${bucket__domain}',
  'use_iam_profile' => true
}
#https://gitlab.com/satorix/omniauth-oauth2-generic
gitlab_rails['omniauth_enabled'] = true
gitlab_rails['omniauth_allow_single_sign_on'] = ['oauth2_generic']
gitlab_rails['omniauth_auto_sign_in_with_provider'] = 'oauth2_generic'
gitlab_rails['omniauth_block_auto_created_users'] = false
gitlab_rails['omniauth_providers'] = [{
  'name' => 'oauth2_generic',
  'app_id' => '${sso__id}',
  'app_secret' => '${sso__secret}',
  'redirect_url' => 'https://${external_domain}/auth/oauth2_generic/callback',
  'args' => {
    client_options: {
      'site' => 'https://${sso__domain}',
      'authorize_url': '/o/authorize/',
      'token_url': '/o/token/',
      'user_info_url' => '/api/v1/user/me/'
    },
    user_response_structure: {
      root_path: [],
      id_path: ['user_id'],
    }
  }
}]
