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
            echo "🔥 Build failed! Waking up the Healer Agent..."
            // We run the python script directly on the Jenkins host
            sh 'python3 healer.py'
        }
        success {
            echo "✅ Build passed! Agent remains asleep."
        }
    }
}