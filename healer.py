# healer.py
import os
import sys

def analyze_failure():
    # Jenkins automatically provides these environment variables during a build
    job_name = os.environ.get('JOB_NAME', 'Unknown Job')
    build_url = os.environ.get('BUILD_URL', 'Unknown URL')
    
    print("\n" + "="*50)
    print("🚨 HEALER AGENT ACTIVATED 🚨")
    print(f"Detected failure in: {job_name}")
    print(f"Log location: {build_url}console")
    print("="*50)
    
    # In the next phase, we will write code here to pull the log
    # and send it to an LLM for analysis.
    print("Mock AI Analysis: The Dockerfile failed to build because of a typo in line 4.")
    print("Suggested Fix: Change 'RUN ppi install' to 'RUN pip install'")
    print("="*50 + "\n")

if __name__ == "__main__":
    analyze_failure()