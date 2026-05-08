pipeline {
    agent any

    environment {
        // Securely maps your Jenkins Credential to an environment variable
        // Make sure the ID 'GITHUB_BOT_TOKEN' exists in Jenkins Credentials
        GITHUB_TOKEN = credentials('GITHUB_BOT_TOKEN')
    }

    stages {
        stage('Environment Check') {
            steps {
                echo "Running pre-flight checks..."
                sh "echo 'Environment looks good.'"
            }
        }

        stage('Dynamic Build & Test') {
            steps {
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
            
            script {
                // RE-ANCHOR CONTEXT: This node block gives the 'sh' steps access to the workspace
                // This prevents the 'Required context class hudson.FilePath is missing' error.
                node(env.NODE_NAME) {
                    
                    // 1. Capture the Git URL for the healer script
                    env.GIT_URL = sh(script: "git config --get remote.origin.url", returnStdout: true).trim()
                    
                    sh '''
                        # 2. Ensure virtual environment exists
                        if [ ! -d "venv" ]; then
                            python3 -m venv venv
                        fi
                        
                        # 3. Install/Update dependencies
                        ./venv/bin/python3 -m pip install --upgrade pip
                        if [ -f "requirements.txt" ]; then
                            ./venv/bin/pip install -r requirements.txt
                        fi
                        
                        # 4. Trigger the Autonomous Multi-File Agent
                        # GITHUB_TOKEN is inherited from the top-level environment block
                        ./venv/bin/python3 healer.py
                    '''
                }
            }
        }
    }
}