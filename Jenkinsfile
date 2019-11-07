pipeline {
  agent none

  stages {
    stage('prepare') {
      agent any
      steps {
        checkout scm
        script {
          pullRequestNumber = sh(
              script: "git log -1 --pretty=%B | grep 'Merge pull request' | cut -d ' ' -f 4 | tr -cd '[[:digit:]]'",
              returnStdout: true
          ).trim()
          currentBuild.displayName = "#${env.BUILD_ID} - PR #${pullRequestNumber}"
        }
      }
    }


    stage('release: dev') {
      steps {
        build job: "data-workspace-dev", parameters: [
          string(name: "DockerTag", value: "master"),
        ]
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

      steps {
        build job: "data-workspace-staging", parameters: [
          string(name: "DockerTag", value: "master"),
        ]
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

      steps {
        build job: "data-workspace-prod", parameters: [
          string(name: "DockerTag", value: "master"),
        ]
      }
    }

  }
}
