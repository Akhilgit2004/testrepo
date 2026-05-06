pipeline {
    agent any
    stages {
        stage('Build Image') {
            steps {
                echo 'Building Docker Image...'
                sh 'docker build -t healer-agent:latest .'
            }
        }
        stage('Test Container (Intended to Fail)') {
            steps {
                echo 'Running a health check...'
                // THIS WILL FAIL because 'typo-image' doesn't exist
                sh 'docker run --rm typo-image:latest python3 -c "print(\'Hello\')"'
            }
        }
    }
    // This is the Watcher. It runs after all stages are complete.
    post {
    failure {
        echo "🔥 Build failed! Setting up Healer environment for Jenkins user..."
        sh '''
            # 1. Create a venv inside the Jenkins workspace
            python3 -m venv venv
            
            # 2. Use the venv's pip to install requests
            ./venv/bin/pip install requests
            
            # 3. Use the venv's python to run your healer script
            ./venv/bin/python3 healer.py
        '''
        }
    }
}