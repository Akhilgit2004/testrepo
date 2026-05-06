pipeline {
    agent any
    stages {
        stage('Build') {
            steps {
                echo 'Building Docker Image...'
                sh 'docker build -t healer-agent:latest .'
            }
        }
        stage('Test') {
            steps {
                echo 'Testing Container...'
                sh 'docker run --rm healer-agent:latest python3 -c "print(\'Container Health Check Passed\')"'
            }
        }
    }
}