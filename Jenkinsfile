pipeline {
  agent none

  parameters {
    string(name: 'GIT_COMMIT', defaultValue: 'master', description: 'Commit SHA or origin branch to deploy')
  }

  stages {
    stage('build') {
      agent {
        kubernetes {
        defaultContainer 'jnlp'
        yaml """
            apiVersion: v1
            kind: Pod
            metadata:
              labels:
                job: ${env.JOB_NAME}
                job_id: ${env.BUILD_NUMBER}
            spec:
              nodeSelector:
                role: worker
              containers:
              - name: builder
                image: gcr.io/kaniko-project/executor:debug
                imagePullPolicy: Always
                command:
                - cat
                tty: true
                volumeMounts:
                - name: jenkins-docker-cfg
                  mountPath: /kaniko/.docker
              volumes:
              - name: jenkins-docker-cfg
                configMap:
                  name: docker-config
                  items:
                  - key: config.json
                    path: config.json
        """
        }
      }
      steps {
        checkout([
            $class: 'GitSCM',
            branches: [[name: params.GIT_COMMIT]],
            userRemoteConfigs: [[url: 'https://github.com/uktrade/data-workspace-frontend.git']]
        ])
        script {
          pullRequestNumber = sh(
              script: "git log -1 --pretty=%B | grep 'Merge pull request' | cut -d ' ' -f 4 | tr -cd '[[:digit:]]'",
              returnStdout: true
          ).trim()
          currentBuild.displayName = "#${env.BUILD_ID} - PR #${pullRequestNumber}"
        }
        lock("data-workspace-build-admin") {
          container(name: 'builder', shell: '/busybox/sh') {
            withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'DATASCIENCE_ECS_DEPLOY']]) {
              withEnv(['PATH+EXTRA=/busybox:/kaniko']) {
                sh """
                  #!/busybox/sh
                  /kaniko/executor \
                    --dockerfile ${env.WORKSPACE}/Dockerfile \
                    -c ${env.WORKSPACE} \
                    --destination=165562107270.dkr.ecr.eu-west-2.amazonaws.com/analysisworkspace-dev-admin:${params.GIT_COMMIT} \
                    --destination=165562107270.dkr.ecr.eu-west-2.amazonaws.com/data-workspace-staging-admin:${params.GIT_COMMIT} \
                    --destination=165562107270.dkr.ecr.eu-west-2.amazonaws.com/jupyterhub-admin:${params.GIT_COMMIT} \
                    --cache=true \
                    --cache-repo=165562107270.dkr.ecr.eu-west-2.amazonaws.com/data-workspace-admin-cache \
                    --skip-unused-stages=true \
                    --target=live
                  """
              }
            }
          }
        }
      }
    }


    stage('release: staging') {
      when {
          expression {
              milestone label: "release-staging"
              input message: 'Deploy to staging?'
              return true
          }
          beforeAgent true
      }

      parallel {
        stage('release: data-workspace') {
          steps {
            ecs_pipeline_admin("data-workspace-staging", params.GIT_COMMIT)
          }
        }
        stage('release: data-workspace-celery') {
          steps {
            ecs_pipeline_celery("data-workspace-staging", params.GIT_COMMIT)
          }
        }
      }
    }


    stage('release: prod') {
      when {
          expression {
              milestone label: "release-prod"
              input message: 'Deploy to prod?'
              return true
          }
          beforeAgent true
      }

      parallel {
        stage('release: data-workspace') {
          steps {
            ecs_pipeline_admin("jupyterhub", params.GIT_COMMIT)
          }
        }
        stage('release: data-workspace-celery') {
          steps {
            ecs_pipeline_celery("jupyterhub", params.GIT_COMMIT)
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
