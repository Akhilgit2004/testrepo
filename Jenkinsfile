pipeline {
    agent any

    // Optional: If you haven't set GITHUB_PAT globally in Jenkins, 
    // make sure it's injected here or in your Jenkins credentials store.

    stages {
        stage('Environment Check') {
            steps {
                echo "Running pre-flight checks..."
                // Just a dummy step to show the pipeline starting
                sh "echo 'Environment looks good.'"
            }
        }

        stage('Test App') {
            steps {
                sh "python3 test.py" // This will throw a NameError
            }
        }
    }

    post {
        failure {
            echo "🔥 Build failed! Initiating Two-Stage Healer Agent..."
            sh '''
                # 1. Ensure virtual environment exists
                python3 -m venv venv
                
                # 2. Install dependencies (requests is needed for Ollama API)
                ./venv/bin/pip install requests
                
                # 3. Trigger the Multi-Agent recovery
                ./venv/bin/python3 healer.py
            '''
        }
    }
}