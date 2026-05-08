import os
import requests
import subprocess
import re

# ==========================================
# CONFIGURATION
# ==========================================
MODEL = "qwen3:14b"
MAX_RETRIES = 2

# ==========================================
# UTILITY FUNCTIONS
# ==========================================

def get_latest_jenkins_log():
    """Fetches the latest Jenkins build log with a larger buffer."""
    job_name = os.environ.get('JOB_NAME', 'unknown_job')
    build_id = os.environ.get('BUILD_ID', 'unknown_build')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            # INCREASED: Fetches 500 lines to see past the virtualenv setup noise
            return "".join(lines[-500:])
    except Exception as e:
        return f"Could not read log: {e}"

def verify_fix(target_file):
    """Dynamically detects the build system and verifies the code."""
    print(f"🔍 VERIFICATION: Analyzing repository to detect build system...")
    
    compile_cmd = []
    
    if os.path.exists("Makefile"):
        compile_cmd = ['make']
    elif os.path.exists("package.json") and not target_file.endswith(".java"):
        compile_cmd = ['npm', 'run', 'build']
    elif os.path.exists("pom.xml"):
        compile_cmd = ['mvn', 'clean', 'compile']
    elif target_file.endswith(".java"):
        compile_cmd = ['javac', target_file]
    elif target_file.endswith(".cpp") or target_file.endswith(".c"):
        compile_cmd = ['g++', target_file, '-o', 'test_build']
    else:
        return True, ""

    result = subprocess.run(compile_cmd, capture_output=True, text=True)
    return (result.returncode == 0, result.stderr)

def create_pull_request(explanation, target_file, attempt):
    """Commits code and opens a GitHub Pull Request using the GITHUB_TOKEN."""
    build_id = os.environ.get('BUILD_ID', 'manual')
    branch_name = f"healer-fix-{build_id}"
    gh_token = os.environ.get('GITHUB_TOKEN')
    repo_url = os.environ.get('GIT_URL')

    try:
        subprocess.run(['git', 'config', 'user.name', 'Healer Agent'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'healer@agent.ai'], check=True)

        if gh_token and repo_url:
            authenticated_url = repo_url.replace("https://", f"https://{gh_token}@")
            subprocess.run(['git', 'remote', 'set-url', 'origin', authenticated_url], check=True)

        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
        subprocess.run(['git', 'add', target_file], check=True)
        subprocess.run(['git', 'commit', '-m', f"fix: AI repair for {target_file}"], check=True)
        subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)
        
        subprocess.run([
            'gh', 'pr', 'create', 
            '--title', f"🤖 AI Fix: {target_file}", 
            '--body', explanation, 
            '--head', branch_name, 
            '--base', 'main'
        ], check=True)
        return True
    except Exception as e:
        print(f"❌ Git Error: {e}")
        return False

def get_fixed_code(file_content, error_log, attempt=1):
    """Sends the code and error to the local LLM."""
    url = "http://localhost:11434/api/generate"
    prompt = f"ERROR LOG:\n{error_log}\n\nSOURCE CODE:\n{file_content}\n\nTASK: Fix bugs and output the whole file in a markdown block."
    payload = {"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1, "num_ctx": 24576}}
    
    try:
        response = requests.post(url, json=payload, timeout=300)
        return response.json().get("response", "")
    except:
        return ""

# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚨 HEALER AGENT: INITIATING RECOVERY...")
    
    log_content = get_latest_jenkins_log()
    
    # IMPROVEMENT: Use word boundaries and broader char set for paths
    potential_files = re.findall(r'(\b[a-zA-Z0-9_./-]+\.(?:cpp|py|java|js|c|h))\b', str(log_content))
    
    target_file = None
    # CRITICAL: Search REVERSED (bottom-up) to find the file from the compiler error, 
    # not the build-system detection log at the top.
    for file_path in reversed(potential_files):
        if "://" in file_path: continue # Ignore URLs
        if os.path.exists(file_path) and "package" not in file_path:
            target_file = file_path
            print(f"🎯 Target confirmed: {target_file}")
            break

    if not target_file:
        print("💀 ERROR: No valid target file found in the logs. Aborting.")
        exit(1)

    with open(target_file, 'r') as f:
        original_code = f.read()

    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 ATTEMPT {attempt}/{MAX_RETRIES}...")
        raw_response = get_fixed_code(original_code, log_content, attempt)
        
        # Robust triple-backtick extraction
        code_block_match = re.search(r"`{3}(?:[a-zA-Z0-9_+-]+)?\n(.*?)\n`{3}", raw_response, re.DOTALL)
        
        if code_block_match:
            fixed_code = code_block_match.group(1).strip()
            with open(target_file, 'w') as f:
                f.write(fixed_code)
                
            verified, errors = verify_fix(target_file)
            if verified:
                print("✅ VERIFIED: Fix compiled successfully!")
                create_pull_request(f"AI fixed {target_file}", target_file, attempt)
                success = True
                break
            else:
                print(f"❌ Verification failed. Reverting...")
                with open(target_file, 'w') as f:
                    f.write(original_code)
        else:
            print("❌ No code block found in AI response.")

    if not success:
        print("💀 ALL ATTEMPTS FAILED.")
    print("="*50)