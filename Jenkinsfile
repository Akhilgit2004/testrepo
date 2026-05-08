pipeline {
    agent any

    stages {
        stage('Environment Check') {
            steps {
                echo "Running pre-flight checks..."
            }
        }

        stage('Dynamic Build & Test') {
            steps {
                sh '''#!/bin/bash
                    # TURN OFF COMMAND TRACING: This prevents Jenkins from printing 
                    # all the "package.json" and "Makefile" checks to the console log.
                    set +x
                    
                    echo "🔍 CI/CD: Detecting build system..."
                    
                    if [ -f "Makefile" ]; then
                        echo "🛠️ Make detected"
                        make
                    elif [ -f "package.json" ]; then
                        echo "🛠️ npm detected"
                        npm install && npm run build
                    elif [ -f "pom.xml" ]; then
                        echo "🛠️ Maven detected"
                        mvn clean compile
                    elif [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
                        echo "🛠️ Gradle detected"
                        if [ -f "gradlew" ]; then
                            ./gradlew build
                        else
                            gradle build
                        fi
                    # Fallbacks for standalone scripts
                    elif ls *.java 1> /dev/null 2>&1; then
                        echo "🛠️ Standalone Java detected"
                        javac *.java
                    elif ls *.cpp 1> /dev/null 2>&1; then
                        echo "🛠️ Standalone C++ detected"
                        g++ *.cpp -o app
                    elif ls *.py 1> /dev/null 2>&1; then
                        echo "🛠️ Standalone Python detected"
                        python3 -m py_compile *.py
                    else
                        echo "❌ No standard project files found!"
                        exit 1
                    fi
                '''
            }
        }
    }

    post {
        failure {
            echo "🔥 Build failed! Initiating AI SRE Agent..."
            
            script {
                // Since 'agent any' is used at the top, we are already in the workspace.
                // We capture the Git URL so the Python script knows where to push.
                env.GIT_URL = sh(script: "git config --get remote.origin.url", returnStdout: true).trim()
                
                sh '''
                    # 1. Ensure virtual environment exists
                    if [ ! -d "venv" ]; then
                        python3 -m venv venv
                    fi
                    
                    # 2. Update pip and install dependencies
                    ./venv/bin/python3 -m pip install --upgrade pip
                    if [ -f "requirements.txt" ]; then
                        ./venv/bin/pip install -r requirements.txt
                    fi
                    
                    # 3. Trigger Hybrid Healer in unbuffered mode
                    # Ensure GITHUB_TOKEN is set in Manage Jenkins -> System -> Global Properties
                    ./venv/bin/python3 -u healer.py
                '''
            }
        }
    }
}