pipeline {
    agent any
    stages {
        stage('Compile C++ App') {
            steps {
                echo "Compiling test.cpp..."
                // This will fail because <numeric> is missing
                sh "g++ app.cpp -o app"
            }
        }
        stage('Run App') {
            steps {
                sh "./app"
            }
        }
    }
    post {
        failure {
            echo "🚨 Compilation Failed. Summoning Healer..."
            sh '''
                ./venv/bin/python3 healer.py
            '''
        }
    }
}