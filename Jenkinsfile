pipeline {
    agent any

    stages {
        stage('Build Image') {
            steps {
                echo "Environment check..."
                sh "docker build -t healer-agent:latest ."
            }
        }

        stage('Compile C++ App (Intended to Fail)') {
            steps {
                echo "Compiling app.cpp..."
                // This will fail with a C++ compiler error
                sh "g++ app.cpp -o app"
            }
        }
    }

    post {
        failure {
            echo "🔥 Build failed! Initiating Healer Agent..."
            sh '''
                ./venv/bin/python3 healer.py
            '''
        }
    }
}