pipeline {
    agent any

    stages {
        stage('Build Image') {
            steps {
                echo "Building Docker Image (Environment check)..."
                sh "docker build -t healer-agent:latest ."
            }
        }

        stage('Test Application (Intended to Fail)') {
            steps {
                echo "Running application tests..."
                // This will crash because app.py has a missing parenthesis
                sh "python3 app.py"
            }
        }
    }

    post {
        failure {
            echo "🔥 Build failed! Initiating Qwen2.5-Coder Healer Agent..."
            sh '''
                # Initialize Python Virtual Environment for the Agent
                python3 -m venv venv
                ./venv/bin/pip install requests
                
                # Execute the Agent
                ./venv/bin/python3 healer.py
            '''
        }
    }
}