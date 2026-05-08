pipeline {
    agent any

    stages {
        stage('Environment Check') {
            steps {
                echo "Running pre-flight checks..." [cite: 1]
            }
        }

        stage('Dynamic Build & Test') {
            steps {
                sh '''
                    echo "🔍 CI/CD: Detecting build system..." [cite: 2]
                    
                    if [ -f "Makefile" ]; then [cite: 2, 3]
                        echo "🛠️ Make detected" [cite: 3]
                        echo "--- REAL BUILD START ---"
                        make [cite: 3]
                    elif [ -f "package.json" ]; then [cite: 3, 4]
                        echo "🛠️ npm detected" [cite: 4]
                        echo "--- REAL BUILD START ---"
                        npm install && npm run build [cite: 4]
                    elif [ -f "pom.xml" ]; then [cite: 4, 5]
                        echo "🛠️ Maven detected" [cite: 5]
                        echo "--- REAL BUILD START ---"
                        mvn clean compile [cite: 5]
                    elif [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then [cite: 5, 6]
                        echo "🛠️ Gradle detected" [cite: 6]
                        echo "--- REAL BUILD START ---"
                        if [ -f "gradlew" ]; then [cite: 6, 7]
                            ./gradlew build [cite: 7]
                        else
                            gradle build [cite: 7]
                        fi [cite: 8]
                    # Fallbacks for standalone scripts
                    elif ls *.java 1> /dev/null 2>&1; then [cite: 8, 9]
                        echo "🛠️ Standalone Java detected" 
                        echo "--- REAL BUILD START ---"
                        javac *.java 
                    elif ls *.cpp 1> /dev/null 2>&1; then [cite: 9, 10]
                        echo "🛠️ Standalone C++ detected" [cite: 10]
                        echo "--- REAL BUILD START ---"
                        g++ *.cpp -o app [cite: 10]
                    elif ls *.py 1> /dev/null 2>&1; then [cite: 10, 11]
                        echo "🛠️ Standalone Python detected" [cite: 11]
                        echo "--- REAL BUILD START ---"
                        python3 -m py_compile *.py [cite: 11]
                    else [cite: 11]
                        echo "❌ No standard project files found!" [cite: 12]
                        exit 1 [cite: 12]
                    fi [cite: 12]
                '''
            }
        }
    }

    post {
        failure {
            echo "🔥 Build failed! Initiating AI SRE Agent..." [cite: 12, 13]
            
            // This script block ensures the Agent runs in the correct workspace context [cite: 15]
            script { [cite: 15]
                node(env.NODE_NAME) { [cite: 15]
                    // Capture the Git URL so the script knows where to push the PR [cite: 15]
                    env.GIT_URL = sh(script: "git config --get remote.origin.url", returnStdout: true).trim() [cite: 15]
                    
                    sh '''
                        # 1. Ensure virtual environment exists [cite: 16]
                        if [ ! -d "venv" ]; then [cite: 16, 17]
                            python3 -m venv venv [cite: 17]
                        fi [cite: 17]
                        
                        # 2. Update pip and install dependencies [cite: 18]
                        ./venv/bin/python3 -m pip install --upgrade pip [cite: 18]
                        if [ -f "requirements.txt" ]; then [cite: 18, 19]
                            ./venv/bin/pip install -r requirements.txt [cite: 19]
                        fi [cite: 19]
                        
                        # 3. Trigger Healer in unbuffered mode [cite: 20]
                        # Ensure GITHUB_TOKEN is set in Manage Jenkins -> System -> Global Properties 
                        ./venv/bin/python3 -u healer.py [cite: 21]
                    '''
                } [cite: 21]
            } [cite: 21]
        }
    }
}