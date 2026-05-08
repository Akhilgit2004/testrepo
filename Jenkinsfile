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
            
            // REMOVED withCredentials wrapper to bypass the ID error.
            // Ensure GITHUB_TOKEN is set in Manage Jenkins -> System -> Global Properties.
            script {
                node(env.NODE_NAME) {
                    // Capture the Git URL
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
                        
                        # 3. Trigger Healer in unbuffered mode. 
                        # It will look for the global GITHUB_TOKEN automatically.
                        ./venv/bin/python3 -u healer.py
                    '''
                }
            }
        }
    }
}