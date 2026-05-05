pipeline {
    agent any
    stages {
        stage('Build Image') {
            steps {
                echo 'Building Docker Image...'
                sh 'docker build -t healer-agent:latest .'
            }
        }
        stage('Test Container') {
            steps {
                echo 'Running a quick health check...'
                sh 'docker run --rm healer-agent:latest python3 -c "print(\'Agent Container is Alive and Well!\')"'
            }
        }
    }
}
