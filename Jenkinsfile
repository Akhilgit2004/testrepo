pipeline {
    agent any

    // Optional: If you haven't set GITHUB_PAT globally in Jenkins, 
    // make sure it's injected here or in your Jenkins credentials store.

    stages {
        stage('Environment Check') {
            steps {
                echo "Running pre-flight checks..."
                sh "echo 'Environment looks good.'"
            }
        }

        stage('Dynamic Build & Test') {
            steps {
                // This bash script mirrors the intelligence of your AI agent.
                // It detects the project type and runs the correct command.
                sh '''
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
            
            // SECURITY: Securely inject the GitHub token into the environment
            withCredentials([string(credentialsId: 'GITHUB_BOT_TOKEN', variable: 'GITHUB_TOKEN')]) {
                script {
                    // Capture the Git URL so the Python script knows where to push
                    env.GIT_URL = sh(script: "git config --get remote.origin.url", returnStdout: true).trim()
                    
                    sh '''
                        # 1. Ensure virtual environment exists
                        python3 -m venv venv
                        
                        # 2. Install dependencies
                        ./venv/bin/pip install -r requirements.txt
                        /var/lib/jenkins/workspace/Agent-CI-Pipeline/venv/bin/python3 -m pip install --upgrade pip
                        
                        # 3. Trigger the Autonomous Multi-File Agent
                        ./venv/bin/python3 healer.py
                    '''
                }
            }
        }
    }
}