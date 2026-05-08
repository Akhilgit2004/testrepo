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
                        echo "--- REAL BUILD START ---"
                        make
                    elif [ -f "package.json" ]; then
                        echo "🛠️ npm detected"
                        echo "--- REAL BUILD START ---"
                        npm install && npm run build
                    elif [ -f "pom.xml" ]; then
                        echo "🛠️ Maven detected"
                        echo "--- REAL BUILD START ---"
                        mvn clean compile
                    elif [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
                        echo "🛠️ Gradle detected"
                        echo "--- REAL BUILD START ---"
                        if [ -f "gradlew" ]; then
                            ./gradlew build
                        else
                            gradle build
                        fi
                    # Fallbacks for standalone scripts
                    elif ls *.java 1> /dev/null 2>&1; then
                        echo "🛠️ Standalone Java detected"
                        echo "--- REAL BUILD START ---"
                        javac *.java
                    elif ls *.cpp 1> /dev/null 2>&1; then
                        echo "🛠️ Standalone C++ detected"
                        echo "--- REAL BUILD START ---"
                        g++ *.cpp -o app
                    elif ls *.py 1> /dev/null 2>&1; then
                        echo "🛠️ Standalone Python detected"
                        echo "--- REAL BUILD START ---"
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
                // We just use 'script' to assign the Git URL to an environment variable.
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
                    
                    # 3. Trigger Healer in unbuffered mode
                    # This will now correctly find GITHUB_TOKEN in Global Properties
                    ./venv/bin/python3 -u healer.py
                '''
            }
        }
    }
}