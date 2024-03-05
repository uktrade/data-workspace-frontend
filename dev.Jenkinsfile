pipeline {
  agent none

  parameters {
    string(name: 'GIT_COMMIT', defaultValue: 'master', description: 'Commit SHA or origin branch to deploy')
  }

  stages {
    stage('build') {      
      steps {
        echo 'Pulling... ' + env.GIT_BRANCH

        echo 'Pulling... ' + env.CHANGE_BRANCH
      }
    }

    stage('release: dev') {      
      when {
        branch 'master'
        beforeAgent true
      }
      parallel {
        stage('release: data-workspace') {
          steps {
            ecs_pipeline_admin("analysisworkspace-dev", params.GIT_COMMIT)
          }
        }
        stage('release: data-workspace-celery') {
          steps {
            ecs_pipeline_celery("analysisworkspace-dev", params.GIT_COMMIT)
          }
        }
      }
    }
  }
}

void ecs_pipeline_admin(cluster, version) {
  lock("data-workspace-ecs-pipeline-${cluster}-admin") {
    build job: "ecs-pipeline", parameters: [
        string(name: "Image", value: "165562107270.dkr.ecr.eu-west-2.amazonaws.com/${cluster}-admin:${version}"),
        string(name: "Cluster", value: cluster),
        string(name: "Service", value: "${cluster}-admin"),
        string(name: "CredentialsId", value: "DATASCIENCE_ECS_DEPLOY"),
        string(name: "EcsPipelineRepository", value: "public.ecr.aws/j9o7k4h4/ecs-pipeline:latest")
    ]
  }
}

void ecs_pipeline_celery(cluster, version) {
  lock("data-workspace-ecs-pipeline-${cluster}-celery") {
    build job: "ecs-pipeline", parameters: [
        string(name: "Image", value: "165562107270.dkr.ecr.eu-west-2.amazonaws.com/${cluster}-admin:${version}"),
        string(name: "Cluster", value: cluster),
        string(name: "Service", value: "${cluster}-admin-celery"),
        string(name: "CredentialsId", value: "DATASCIENCE_ECS_DEPLOY"),
        string(name: "EcsPipelineRepository", value: "public.ecr.aws/j9o7k4h4/ecs-pipeline:latest")
    ]
  }
}
