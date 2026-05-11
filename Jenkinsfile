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
                    # TURN OFF COMMAND TRACING: Keeps logs clean
                    set +x
                    
                    echo "🔍 CI/CD: Initiating Global Workspace Scan..."
                    
                    # This flag tracks if ANY build process fails across the entire workspace
                    BUILD_FAILED=0

                    # 1. Check C++
                    if ls *.cpp 1> /dev/null 2>&1; then
                        echo "🛠️ Compiling C++ files..."
                        if ! g++ *.cpp -o app; then
                            echo "❌ C++ Compilation Failed"
                            BUILD_FAILED=1
                        fi
                    fi

                    # 2. Check Maven (Prioritize over Standalone Java)
                    if [ -f "pom.xml" ]; then
                        echo "🛠️ Running Maven Build..."
                        if ! mvn clean compile; then
                            echo "❌ Maven Build Failed"
                            BUILD_FAILED=1
                        fi
                    fi

                    # 3. Check Gradle (Prioritize over Standalone Java)
                    if [ -f "build.gradle" ] || [ -f "build.gradle.kts" ]; then
                        echo "🛠️ Running Gradle Build..."
                        if [ -f "gradlew" ]; then
                            if ! ./gradlew build; then
                                echo "❌ Gradle Build Failed"
                                BUILD_FAILED=1
                            fi
                        else
                            if ! gradle build; then
                                echo "❌ Gradle Build Failed"
                                BUILD_FAILED=1
                            fi
                        fi
                    fi

                    # 4. Check Java (Standalone - ONLY if no Maven or Gradle is found)
                    if [ ! -f "pom.xml" ] && [ ! -f "build.gradle" ] && [ ! -f "build.gradle.kts" ]; then
                        if ls *.java 1> /dev/null 2>&1; then
                            echo "🛠️ Compiling Standalone Java files..."
                            if ! javac *.java; then
                                echo "❌ Java Compilation Failed"
                                BUILD_FAILED=1
                            fi
                        fi
                    fi

                    # 5. Check npm
                    if [ -f "package.json" ]; then
                        echo "🛠️ Running npm Build..."
                        if ! (npm install && npm run build); then
                            echo "❌ npm Build Failed"
                            BUILD_FAILED=1
                        fi
                    fi

                    # 6. Check Make
                    if [ -f "Makefile" ]; then
                        echo "🛠️ Running Make..."
                        if ! make; then
                            echo "❌ Make Failed"
                            BUILD_FAILED=1
                        fi
                    fi

                    # 7. Check Python
                    if ls *.py 1> /dev/null 2>&1; then
                        echo "🛠️ Verifying Python Scripts..."
                        if ! python3 -m py_compile *.py; then
                            echo "❌ Python Syntax Check Failed"
                            BUILD_FAILED=1
                        fi
                    fi

                    # ==========================================
                    # FINAL VERDICT
                    # ==========================================
                    if [ $BUILD_FAILED -eq 1 ]; then
                        echo "🚨 Global Scan complete: Failures detected."
                        exit 1  # This triggers your AI Healer!
                    else
                        echo "✅ Global Scan complete: All systems nominal."
                    fi
                '''
            }
        }
    }

    post {
        failure {
            echo "🔥 Build failed! Initiating AI SRE Agent..."
            
            script {
                // Capture the Git URL so the Python script knows where to push.
                env.GIT_URL = sh(script: "git config --get remote.origin.url", returnStdout: true).trim()
                
                sh '''
                    # 1. Ensure virtual environment exists
                    if [ ! -d "venv" ]; then
                        python3 -m venv venv
                    fi
                    
                    # 2. Trigger Hybrid Healer in unbuffered mode
                    ./venv/bin/python3 -u healer.py
                '''
            }
        }
    }
}