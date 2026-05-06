import os
import requests

def get_latest_jenkins_log():
    # Jenkins provides these env vars during a build
    job_name = os.environ.get('JOB_NAME')
    build_id = os.environ.get('BUILD_ID')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            # Get the last 50 lines to keep the context window small and fast
            lines = f.readlines()
            return "".join(lines[-50:])
    except Exception as e:
        return f"Could not read log: {e}"

def ask_codegemma(error_log):
    url = "http://localhost:11434/api/generate"
    prompt = f"Analyze this Jenkins CI/CD error and provide a specific fix:\n\n{error_log}"
    
    payload = {"model": "codegemma:7b", "prompt": prompt, "stream": False}
    
    response = requests.post(url, json=payload)
    return response.json().get("response")

if __name__ == "__main__":
    print("🚨 HEALER AGENT: ANALYZING NATIVE FEDORA BUILD FAILURE...")
    log_content = get_latest_jenkins_log()
    solution = ask_codegemma(log_content)
    print(f"🤖 AI SUGGESTION:\n{solution}")