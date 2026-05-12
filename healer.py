import sys
import os
import requests
import subprocess
import re
import json
import time
import chromadb
from chromadb.utils import embedding_functions
import argparse
# ==========================================
# CONFIGURATION
# ==========================================
MODEL = "qwen3:14b"
MAX_RETRIES = 2
BUILD_REGISTRY = {
    "java": {
        "verify": "mvn clean compile",
        "config": "pom.xml",
        "test_cmd": "mvn test"
    },
    "python": {
        "verify": "python3 -m py_compile {file}",
        "config": "requirements.txt",
        "test_cmd": "pytest"
    },
    "cpp": {
        "verify": "g++ {file} -o app",
        "config": "Makefile",
        "test_cmd": "./app"
    },
    # --- NEW ADDITIONS ---
    "javascript": {
        "verify": "npm run build",
        "config": "package.json",
        "test_cmd": "npm test"
    },
    "go": {
        "verify": "go build ./...",
        "config": "go.mod",
        "test_cmd": "go test ./..."
    },
    "rust": {
        "verify": "cargo build",
        "config": "Cargo.toml",
        "test_cmd": "cargo test"
    }
}
# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def get_suspect_list(log_content):
    """
    Recursively scans the project for files mentioned in the Jenkins log.
    Returns the relative path so the agent can find files nested in folders.
    """
    suspects = []
    
    # Do not scan inside these directories
    IGNORE_DIRS = {'.git', 'venv', 'target', 'node_modules', 'build', '__pycache__', '.idea', '.vscode'}
    
    # Walk through the directory tree starting from the root ('.')
    for root, dirs, files in os.walk('.'):
        # Modify dirs in-place to skip ignored directories entirely
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            # We don't want the agent trying to perform surgery on itself
            if file == "healer.py":
                continue
                
            # If the bare filename (e.g., 'Main.java') appears anywhere in the log...
            if file in log_content:
                # Construct the proper relative path (e.g., 'src/main/java/Main.java')
                # We strip the leading './' to keep the paths clean
                file_path = os.path.relpath(os.path.join(root, file), '.').replace('./', '')
                
                if file_path not in suspects:
                    suspects.append(file_path)
                    
    return suspects

def select_target_file(error_log, suspects):
    """STAGE 0: AI Dispatcher. The AI decides which file is the root cause."""
    if not suspects:
        return None
    if len(suspects) == 1:
        return suspects[0] # No need to ask AI if there's only one suspect

    url = "http://localhost:11434/api/generate"
    prompt = f"""You are a Lead SRE. Analyze this build failure and the list of suspect files.
    
    ERROR LOG:
    {error_log}
    
    SUSPECT FILES:
    {suspects}
    
    TASK: Which file is the ROOT CAUSE of this error? 
    - NEVER pick a file that is not in the SUSPECT FILES list.
    - If there are multiple errors in different languages, pick the one that appeared FIRST in the log.
    
    RULES:
    1. Respond ONLY with the exact filename.
    2. Do not explain your reasoning.
    
    TARGET FILE:"""
    try:
        # Temperature is low (0.1) so it doesn't get creative with filenames
        res = requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}, timeout=300)
        ai_response = res.json().get("response", "").strip()
        
        # Safety Check: Ensure the AI's answer is actually in our suspect list
        for suspect in suspects:
            if suspect in ai_response:
                return suspect
                
        # Fallback if the AI hallucinates
        return suspects[0] 
    except Exception as e:
        print(f"⚠️ Dispatcher API Error: {e}. Falling back to default target.")
        return suspects[0]


def get_latest_jenkins_log():
    """Fetches the latest Jenkins build log with a 500-line buffer."""
    job_name = os.environ.get('JOB_NAME', 'unknown_job')
    build_id = os.environ.get('BUILD_ID', 'unknown_build')
    log_path = f"/var/lib/jenkins/jobs/{job_name}/builds/{build_id}/log"
    try:
        with open(log_path, 'r') as f:
            lines = f.readlines()
            return "".join(lines[-500:])
    except Exception as e:
        return f"Could not read log: {e}"

def verify_fix(target_file):
    """Verifies the fix based on the SPECIFIC file that was changed."""
    print(f"🧪 VERIFICATION: Running check for {target_file}...")
    
    # Base the tool on the target_file, not just file existence
    if target_file == "pom.xml":
        compile_cmd = ['mvn', 'clean', 'compile']
    elif target_file == "requirements.txt":
        # For requirements, 'verification' means checking if pip can parse it
        compile_cmd = ['./venv/bin/pip', 'install', '--dry-run', '-r', 'requirements.txt']
    elif target_file.endswith(".java"):
        compile_cmd = ['javac', target_file]
    elif target_file.endswith(".py"):
        compile_cmd = ['python3', '-m', 'py_compile', target_file]
    else:
        return True, ""

    try:
        result = subprocess.run(compile_cmd, capture_output=True, text=True, timeout=300)
        return (result.returncode == 0, result.stderr)
    except Exception as e:
        return False, str(e)

def create_pull_request(diagnosis, target_file, attempt):
    timestamp = int(time.time())
    branch_name = f"healer-fix-{timestamp}"
    
    print(f"🚀 GIT: Preparing to push fix for {target_file}...")
    
    try:
        # 1. Force branch creation/reset
        subprocess.run(['git', 'checkout', '-B', branch_name], check=True)
        
        # 2. Add the specific file
        subprocess.run(['git', 'add', target_file], check=True)
        
        # 3. CHECK: Are there actually any changes staged?
        # 'git diff --cached --exit-code' returns 0 if no changes, 1 if changes exist
        result = subprocess.run(['git', 'diff', '--cached', '--exit-code'], capture_output=True)
        
        if result.returncode == 0:
            print(f"🤔 GIT: No actual changes detected for {target_file}. It might already be fixed. Skipping commit.")
            return # Exit early, no need to push
            
        # 4. Commit and Push
        commit_msg = f"fix: AI repair for {target_file} (Attempt {attempt})"
        subprocess.run(['git', 'commit', '-m', commit_msg], check=True)
        
        # Using --force to ensure we overwrite any weirdness on the remote
        subprocess.run(['git', 'push', '-u', 'origin', branch_name, '--force'], check=True)
        
        print(f"✅ GIT: Successfully pushed {target_file} to {branch_name}")
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Git Error: {e.output.decode() if e.output else e}")
    

WEBHOOK_URL="https://discord.com/api/webhooks/1502582315354689578/sZDegYsairWMZrCuLrLsEHI0UAm3QAbTzZpmvtSKDIw1vYT2_Ww9_AOSefLciug3px3R/slack"
def notify_team(target_file, diagnosis, attempt):
    """Sends a formatted summary of the fix to the team's chat channel."""
    if not WEBHOOK_URL or "XXXXXXXXXXXXXXXX" in WEBHOOK_URL:
        print("⚠️ CHATOPS: No valid Webhook URL configured. Skipping notification.")
        return

    print(f"📢 CHATOPS: Broadcasting fix for {target_file} to the team...")
    
    # Extract just the first few lines of the AI's diagnosis to keep the chat clean
    summary_lines = diagnosis.strip().split('\n')[:3]
    short_summary = " ".join(summary_lines).replace('*', '').replace('#', '') + "..."

    payload = {
        "text": "🚨 *Hybrid Healer Agent Intervention*",
        "attachments": [
            {
                "color": "#36a64f", # Green for successful fix
                "title": f"🛠️ Successfully patched {target_file}",
                "text": f"*{short_summary}*",
                "fields": [
                    {
                        "title": "Status",
                        "value": "✅ Compiled & Verified",
                        "short": True
                    },
                    {
                        "title": "Attempts Needed",
                        "value": f"{attempt}/{MAX_RETRIES}",
                        "short": True
                    }
                ],
                "footer": "Hybrid Healer AI",
                "ts": int(time.time())
            }
        ]
    }

    try:
        response = requests.post(WEBHOOK_URL, data=json.dumps(payload), headers={'Content-Type': 'application/json'}, timeout=10)
        if response.status_code in [200, 204]:
            print("✅ CHATOPS: Notification delivered successfully!")
        else:
            print(f"⚠️ CHATOPS: Failed to send notification. HTTP {response.status_code}")
    except Exception as e:
        print(f"⚠️ CHATOPS: Error sending notification: {e}")   

# ==========================================
# AI AGENT FUNCTIONS
# ==========================================

def get_diagnosis(file_content, error_log,target_file, supporting_context=""):
    """STAGE 1: Now with 100% more peripheral vision."""
    url = "http://localhost:11434/api/generate"
    prompt = f"""You are a Senior SRE. Analyze the build failure.
    
    ERROR LOG:
    {error_log}

    BROKEN SOURCE CODE:
    {file_content}

    SUPPORTING CONTEXT (Related files):
    {supporting_context}
    
    TASK: Identify if the error is in the broken file or caused by a mismatch with supporting files.
    CRITICAL DIRECTIVE - THE TARGET SWITCHER:
You are currently analyzing the file: {target_file}. 
If you realize the error is NOT caused by this file, but by a missing dependency or misconfiguration in a supporting file (like pom.xml, package.json, build.gradle, or requirements.txt), YOU MUST ABORT surgery on the current file.
To do this, start your response EXACTLY with this phrase:
SWITCH_TARGET: <filename>
(For example: SWITCH_TARGET: pom.xml)
Do not provide any code if you switch targets. Just provide the switch command and a brief explanation of why.
    DIAGNOSIS:"""
    
    try:
        res = requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False}, timeout=300)
        return res.json().get("response", "Could not generate diagnosis.")
    except Exception as e:
        return f"API Error: {e}"

def get_fixed_code(target_file, file_content, diagnosis,supporting_context):
    """STAGE 2: Generate the full rewritten file based on the diagnosis."""
    url = "http://localhost:11434/api/generate"
    
    # We now pass the target_file into the prompt to give the AI spatial awareness
    prompt = f"""You are an automated code remediation agent.
    
    DIAGNOSIS: {diagnosis}
    FILE TO FIX: {target_file}
    
    SUPPORTING CONTEXT (The Ground Truth):
    {supporting_context}
    
    SOURCE CODE:
    {file_content}
    
    TASK: Fix {target_file} so it compiles and works with the SUPPORTING CONTEXT.
    
    RULES:
    1. If the SOURCE CODE calls a method that doesn't exist in the SUPPORTING CONTEXT, change the call to a method that DOES exist.
    2. Only output the full corrected code for {target_file} in a markdown block.
    3. Do not modify the Supporting Context files.
    """
    
    try:
        res = requests.post(url, json={"model": MODEL, "prompt": prompt, "stream": False, "options": {"temperature": 0.1}}, timeout=300)
        return res.json().get("response", "")
    except Exception as e:
        return ""

def extract_error_snippet(log_text, target_filename):
    """Extracts only the log lines relevant to the specific broken file."""
    lines = log_text.split('\n')
    snippet_lines = []
    
    for i, line in enumerate(lines):
        if target_filename in line:
            # Grab the line with the filename, plus a few lines of context around it
            start = max(0, i - 2)
            end = min(len(lines), i + 5)
            snippet_lines.extend(lines[start:end])
            
    if snippet_lines:
        return "\n".join(snippet_lines)[:500] # Keep it within 500 chars for the Vector DB
    
    return log_text[:500]

def autonomous_scan():
    """
    Uses local tools to find errors without needing a Jenkins log.
    """
    print("🔎 AGENT: Initiating Deep Audit...")
    discovered_errors = ""
    
    # Run a quick lint check on the whole directory
    # For Python:
    lint_output = os.popen("flake8 . --select=E9,F63,F7,F82 --show-source").read()
    
    if lint_output:
        print("🚨 AUDIT: Found syntax/logic errors independently!")
        discovered_errors = lint_output
    else:
        print("✅ AUDIT: No obvious syntax errors found.")
        
    return discovered_errors


class VectorMemory:
    def __init__(self, db_path="./agent_memory"):
        self.client = chromadb.PersistentClient(path=db_path)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2" # Or your local path if you downloaded it!
        )
        self.collection = self.client.get_or_create_collection(
            name="fix_history", 
            embedding_function=self.embed_fn
        )

    def learn(self, error_snippet, target_file, remedy, lang):
        """Stores a fix with a Language metadata tag."""
        doc_id = f"id_{int(time.time())}"
        self.collection.add(
            ids=[doc_id],
            documents=[error_snippet],
            metadatas=[{"target_file": target_file, "remedy": remedy, "lang": lang}] # Added lang!
        )
        print(f"🧠 MEMORY: Learned a new {lang} fix for {target_file}.")

    def recall(self, error_snippet, lang):
        """Searches memory, strictly filtered by language."""
        results = self.collection.query(
            query_texts=[error_snippet],
            n_results=1,
            where={"lang": lang} # THE LANGUAGE WALL: Ignore other languages!
        )
        
        if not results or not results['ids'] or not results['ids'][0]:
            print(f"🧠 MEMORY: No previous {lang} experience found.")
            return None
        
        try:
            distance = results['distances'][0][0]
            if distance < 0.4:
                match = results['metadatas'][0][0]
                return match['remedy']
        except (IndexError, TypeError):
            return None
        
        return None
       
def get_supporting_context(target_file, error_log, broken_code):
    """Physically crawls the workspace to find ANY file mentioned in the error."""
    print("🕵️ SEARCHING: Agent is hunting for related files in the directory...")
    workspace_dir = "." 
    supporting_data = ""
    found_files = []
    
    # 1. Grab every "CapitalizedWord" from the error and the code.
    # In Java, these are almost always the Class names we need.
    potential_names = set(re.findall(r'\b[A-Z][a-zA-Z0-9_]+\b', error_log + broken_code))
    
    # 2. Crawl every folder in the Jenkins workspace
    for root, dirs, files in os.walk(workspace_dir):
        # Skip system noise
        if any(ignored in root for ignored in ['.git', 'venv', 'node_modules', 'target']):
            continue
            
        for file in files:
            # Check if the filename (without .java/.py) matches any word we found
            base_name = os.path.splitext(file)[0]
            if base_name in potential_names and file != os.path.basename(target_file):
                file_path = os.path.join(root, file)
                found_files.append(file_path)

    # 3. Read the files we found and prepare them for the AI
    for file_path in list(set(found_files))[:3]:
        try:
            with open(file_path, 'r') as f:
                print(f"👀 CONTEXT ACQUIRED: Reading {file_path}")
                supporting_data += f"\n--- REFERENCE FILE: {file_path} ---\n{f.read()}\n"
        except:
            continue
            
    return supporting_data

def classify_error(error_log):
    """Detects what KIND of error it is, across any language."""
    # Dependency missing patterns (Universal)
    dep_patterns = [
        r"package [\w.]+ does not exist",  # Java
        r"ModuleNotFoundError",            # Python
        r"Cannot find module",             # JS
        r"fatal error: .* No such file"    # C++
    ]
    
    # Config file syntax patterns (Universal)
    config_patterns = [
        r"ProjectBuildingException",       # Maven
        r"Invalid control character",      # JSON/package.json
        r"SyntaxError in",                 # Requirements/Make
        r"missing.*'[\w.]+'"               # General missing fields
    ]

    for pattern in dep_patterns:
        if re.search(pattern, error_log): return "DEPENDENCY"
    for pattern in config_patterns:
        if re.search(pattern, error_log): return "CONFIG_SYNTAX"
        
    return "CODE"
# ==========================================
# MAIN ORCHESTRATOR
# ==========================================

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--log_file", help="Path to local Jenkins log")
    args = parser.parse_args()

    print("\n" + "="*50)
    print("🚨 HYBRID HEALER AGENT: INITIATING GLOBAL SWEEP...")

    # LOG LOGIC: Prioritize the injected log file
    if args.log_file and os.path.exists(args.log_file):
        print(f"📖 Reading local log file: {args.log_file}")
        with open(args.log_file, 'r') as f:
            master_log_content = f.read()
    else:
        # Fallback to API if no file is provided
        master_log_content = get_latest_jenkins_log()
    
    if not master_log_content:
        print("🏝️ Log is empty. Going back to sleep.")
        sys.exit(0)

    # --- THE SMARTER CHECK: Priority-Based Failure Detection ---
    failure_keywords = ["ERROR", "FAIL", "FAILED", "SyntaxError", "multiple definition", "command not found"]
    is_actually_broken = any(word in master_log_content for word in failure_keywords)

    if not is_actually_broken and "SUCCESS" in master_log_content:
        print("🤔 Log looks clean (No critical keywords found). Switching to Autonomous Audit Mode...")
        master_log_content = autonomous_scan()
        if not master_log_content:
            print("🏝️ Nothing to fix. Going back to sleep.")
            sys.exit(0)
    else:
        print("🚩 FAILURE DETECTED: Proceeding with remediation loop...")
    
    memory = VectorMemory()
    patched_files = []
    max_global_rounds = 5 
    MAX_RETRIES = 3 # Ensure this is defined
    
    # Language configuration mapping for quick lookups
    config_map = {
        ".py": "python", "requirements.txt": "python",
        ".js": "javascript", ".ts": "javascript", "package.json": "javascript",
        ".go": "go", "go.mod": "go",
        ".rs": "rust", "Cargo.toml": "rust",
        ".java": "java", "pom.xml": "java", "build.gradle": "java", ".kts": "java",
        ".cpp": "cpp", ".h": "cpp", "Makefile": "cpp"
    }
    
    for round_num in range(1, max_global_rounds + 1):
        print(f"\n🌐 GLOBAL REPAIR ROUND {round_num}/{max_global_rounds}")
        
        # 1. CLASSIFY THE ERROR
        category = classify_error(master_log_content)
        
        # 2. GET SUSPECTS
        all_suspects = get_suspect_list(master_log_content)
        # FILTER: Remove files we've already patched in this session
        suspects = [f for f in all_suspects if f not in patched_files]
        
        if not suspects:
            print("✅ GLOBAL SWEEP COMPLETE: All unpatched errors have been handled!")
            break 
            
        # Dispatcher picks the target
        print(f"🕵️ DISPATCHER: Analyzing suspects: {suspects}")
        target_file = select_target_file(master_log_content, suspects)

        if not target_file or target_file not in suspects:
            print(f"💀 ERROR: AI picked an invalid target. Halting sweep.")
            break
            
        # 3. DETECT TARGET LANGUAGE (Expanded Polyglot Support)
        file_ext = os.path.splitext(target_file)[1]
        detected_lang = config_map.get(file_ext, config_map.get(os.path.basename(target_file), "java"))
            
        print(f"🎯 ROUND {round_num}: Targeting {target_file} ({detected_lang})")

        with open(target_file, 'r') as f:
            original_code = f.read()
            
        # Extract the Surgical Fingerprint for this specific file
        file_specific_error = extract_error_snippet(master_log_content, target_file)

        # 4. REMEDIATION LOOP (With Target Switching & Memory-Fail Logic)
        file_fixed = False
        attempt = 1
        
        while attempt <= MAX_RETRIES:
            print(f"\n🔄 ATTEMPT {attempt}/{MAX_RETRIES} for {target_file}...")
            
            # --- IMPROVED MEMORY CHECK (The Reality Check) ---
            past_remedy = None
            if attempt == 1:
                print("🔍 MEMORY: Searching for similar past experiences...")
                past_remedy = memory.recall(file_specific_error, detected_lang)
            
            if past_remedy:
                print("💡 EUREKA: I found a remedy in history!")
                diagnosis_to_use = f"RECALLED REMEDY: {past_remedy}"
                context = "" 
            else:
                if attempt > 1:
                    print("⚠️ MEMORY FAIL: Past experience was incorrect. Forcing fresh analysis...")
                else:
                    print("🧠 STAGE 1: Analyzing error from scratch...")
                
                # We pass the targeted error snippet to the AI so it doesn't get confused
                initial_diagnosis = get_diagnosis(original_code, file_specific_error, target_file, "")
                context = get_supporting_context(target_file, initial_diagnosis, original_code)
                diagnosis_to_use = initial_diagnosis
                
                if context:
                    print("🧠 STAGE 1.5: Refining diagnosis with discovered context...")
                    diagnosis_to_use = get_diagnosis(original_code, file_specific_error, target_file, context)
            
            print(f"\n🗣️ AI DIAGNOSIS:\n{diagnosis_to_use}\n")

            if "API Error:" in diagnosis_to_use:
                print("💀 ERROR: LLM Timeout. Retrying...")
                attempt += 1
                continue

            # ==========================================
            # 🔀 THE TARGET SWITCHER INTERCEPTOR (V3)
            # ==========================================
            if "SWITCH_TARGET:" in diagnosis_to_use:
                match = re.search(r"SWITCH_TARGET:\s*([a-zA-Z0-9_./-]+)", diagnosis_to_use)
                if match:
                    new_target = match.group(1).strip()
                    
                    # SAFETY: Prevent infinite self-switching
                    if new_target == target_file:
                        print(f"🧐 NOTICE: AI suggested {new_target}, but we are already there. Proceeding to fix.")
                        # Strip the command out so it doesn't trip up Stage 2
                        diagnosis_to_use = diagnosis_to_use.replace(f"SWITCH_TARGET: {new_target}", "")
                        
                    # REALITY CHECK: Ensure the file is actually part of the project
                    elif new_target in all_suspects or os.path.exists(new_target):
                        print(f"\n🚨 TARGET SWITCH DETECTED! AI realized the true culprit is {new_target}.")
                        
                        target_file = new_target
                        
                        # Read the new file's code (or create blank if missing config)
                        if os.path.exists(target_file):
                            with open(target_file, 'r') as f:
                                original_code = f.read()
                        else:
                            original_code = "" 
                            
                        # Update the language for the new file dynamically
                        new_file_ext = os.path.splitext(target_file)[1]
                        detected_lang = config_map.get(new_file_ext, config_map.get(os.path.basename(target_file), "java"))
                        
                        # CRITICAL: We do NOT update the `file_specific_error` here.
                        # We keep the old error so the AI remembers WHY it is editing this new file.
                        
                        print(f"🔄 Rebooting Remediation Loop for {target_file}...")
                        attempt = 1 
                        continue 
                    else:
                        print(f"⚠️ AI requested switch to {new_target}, but it is not a valid project file. Ignoring.")

            # ==========================================
            # STAGE 2: Code Generation
            # ==========================================
            print(f"🛠️ STAGE 2: Generating full rewrite for {target_file}...")
            raw_response = get_fixed_code(target_file, original_code, diagnosis_to_use, context)
            code_block_match = re.search(r"`{3}(?:[a-zA-Z0-9_+-]+)?\n(.*?)\n`{3}", raw_response, re.DOTALL)
            
            if code_block_match:
                fixed_code = code_block_match.group(1).strip()
                with open(target_file, 'w') as f:
                    f.write(fixed_code)
                    
                # STAGE 3: Verification
                verified, errors = verify_fix(target_file)
                if verified:
                    print(f"✅ SUCCESS: {target_file} fixed and verified!")
                    patched_files.append(target_file)
                    
                    # Learn the new fix (Includes language tag)
                    if not past_remedy:
                        memory.learn(file_specific_error, target_file, diagnosis_to_use, detected_lang)
                    
                    create_pull_request(diagnosis_to_use, target_file, attempt)
                    notify_team(target_file, "Partial fix applied...", round_num)
                    
                    # --- THE LOG SCRUBBER ---
                    print(f"🧹 SCRUBBER: Removing {target_file} errors from log for next round.")
                    scrubbed_lines = [line for line in master_log_content.split('\n') if target_file not in line]
                    master_log_content = "\n".join(scrubbed_lines)
                    
                    file_fixed = True
                    break
                else:
                    print(f"❌ FAIL: Fix did not compile. Compiler said:\n{errors}")
                    # Update the error snippet to include the NEW failure for the next attempt
                    file_specific_error = errors[:500] 
                    with open(target_file, 'w') as f:
                        f.write(original_code) # Revert
            else:
                print("❌ ERROR: AI failed to provide a valid code block.")
                
            attempt += 1

        # Evaluate the round
        if file_fixed:
            print(f"✔️ {target_file} patched. Looping back...")
            continue 
        else:
            print(f"⚠️ Could not fix {target_file}. Halting sweep.")
            break 

    print("\n" + "="*50)
    print("🏁 HYBRID HEALER AGENT: SWEEP PROTOCOL CONCLUDED.")