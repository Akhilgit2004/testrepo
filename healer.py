import os
import requests
import subprocess
import re
import json
import time
import chromadb
from chromadb.utils import embedding_functions
# ==========================================
# CONFIGURATION
# ==========================================
MODEL = "qwen3:14b"
MAX_RETRIES = 2
BUILD_REGISTRY = {
    "java": {"config": "pom.xml", "tool": "mvn", "check": "mvn clean compile"},
    "python": {"config": "requirements.txt", "tool": "pip", "check": "python3 -m py_compile"},
    "javascript": {"config": "package.json", "tool": "npm", "check": "npm install && npm run build"},
    "cpp": {"config": "Makefile", "tool": "make", "check": "make"}
}
# ==========================================
# UTILITY FUNCTIONS
# ==========================================
def get_suspect_list(error_log):
    """Gathers all files that could possibly be related to the error."""
    # Find any file mentioned in the log (source files, configs, etc.)
    files_in_log = re.findall(r'(\b[a-zA-Z0-9_./-]+\.(?:java|py|js|cpp|h|xml|json|txt))\b', error_log)
    
    # Add standard universal configs just in case they are the culprit
    configs = ["pom.xml", "requirements.txt", "package.json", "Makefile"]
    
    # Combine, deduplicate, and only keep files that physically exist in the workspace
    suspects = list(set([f for f in files_in_log + configs if os.path.exists(f)]))
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
    - If it's a syntax error, typo, or logic bug, pick the source code file.
    - If a library/dependency is truly missing or the build configuration is broken, pick the config file (e.g., pom.xml, requirements.txt).
    
    RULES:
    1. Respond ONLY with the exact filename from the SUSPECT FILES list.
    2. Do not explain your reasoning. Do not use markdown.
    
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

def create_pull_request(explanation, target_file, attempt):
    """Commits code and opens a GitHub Pull Request using GITHUB_TOKEN."""
    build_id = os.environ.get('BUILD_ID', 'manual')
    branch_name = f"healer-fix-{build_id}"
    gh_token = os.environ.get('GITHUB_TOKEN')
    repo_url = os.environ.get('GIT_URL')

    try:
        subprocess.run(['git', 'config', 'user.name', 'Healer Agent'], check=True)
        subprocess.run(['git', 'config', 'user.email', 'healer@agent.ai'], check=True)

        if gh_token and repo_url:
            auth_url = repo_url.replace("https://", f"https://{gh_token}@")
            subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url], check=True)

        subprocess.run(['git', 'checkout', '-b', branch_name], check=True)
        subprocess.run(['git', 'add', target_file], check=True)
        subprocess.run(['git', 'commit', '-m', f"fix: AI repair for {target_file}"], check=True)
        subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True)
        
        pr_body = f"## 🚨 Automated Fix Report\n**Diagnosis:**\n{explanation}"
        subprocess.run(['gh', 'pr', 'create', '--title', f"🤖 AI Fix: {target_file}", '--body', pr_body, '--head', branch_name, '--base', 'main'], check=True)
        return True
    except Exception as e:
        print(f"❌ Git Error: {e}")
        return False
    

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

def get_diagnosis(file_content, error_log, supporting_context=""):
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

class VectorMemory:
    def __init__(self, db_path="./agent_memory"):
        # Initialize the local database
        self.client = chromadb.PersistentClient(path=db_path)
        
        # Use a lightweight, local embedding function (no API cost)
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        
        # Create or load the 'experience' collection
        self.collection = self.client.get_or_create_collection(
            name="fix_history", 
            embedding_function=self.embed_fn
        )

    def learn(self, error_log, target_file, remedy):
        """Stores a successful fix in the vector store."""
        doc_id = f"id_{int(time.time())}"
        self.collection.add(
            ids=[doc_id],
            documents=[error_log[:500]],
            metadatas=[{"target_file": target_file, "remedy": remedy}]
        )
        print(f"🧠 MEMORY: Learned a new fix for {target_file}.")

    def recall(self, current_error):
        """Searches for semantically similar errors with safety checks."""
        # Query the database
        results = self.collection.query(
            query_texts=[current_error[:500]],
            n_results=1
        )
        
        # Check if we actually got a result back
        # results['ids'][0] will be empty [] if no matches are found
        if not results or not results['ids'] or not results['ids'][0]:
            print("🧠 MEMORY: No previous experience found (Database might be empty).")
            return None
        
        # Now it is safe to check the distance
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
    print("\n" + "="*50)
    print("🚨 HYBRID HEALER AGENT: INITIATING RECOVERY...")
    
    # 0. Initialize Vector Knowledge Base
    memory = VectorMemory()
    
    log_content = get_latest_jenkins_log()
    
    # 1. CLASSIFY THE ERROR
    category = classify_error(log_content)
    
    # 2. DETECT LANGUAGE & CONFIG NAME
    detected_lang = "java" # Default fallback
    if "python" in log_content.lower() or ".py" in log_content:
        detected_lang = "python"
    elif "npm" in log_content.lower() or "node" in log_content.lower() or ".js" in log_content:
        detected_lang = "javascript"
    elif "g++" in log_content.lower() or "gcc" in log_content.lower() or ".cpp" in log_content:
        detected_lang = "cpp"
        
    config_name = BUILD_REGISTRY[detected_lang]["config"]
    target_file = None

    # 3. AI TARGET DISPATCHER
    suspects = get_suspect_list(log_content)
    
    # Edge Case: The build failed because the config file is missing entirely
    if category in ["DEPENDENCY", "CONFIG_SYNTAX"] and not os.path.exists(config_name):
        print(f"📁 NOTICE: {config_name} is missing entirely. Creating an empty file for the AI...")
        with open(config_name, 'w') as f:
            f.write("") # Blank slate for the AI to populate
        target_file = config_name
    else:
        # Standard flow: Let the AI pick from the existing suspects
        print(f"🕵️ DISPATCHER: Analyzing suspects: {suspects}")
        target_file = select_target_file(log_content, suspects)

    if not target_file:
        print("💀 ERROR: No suspect files found and AI could not identify a target. Aborting.")
        exit(1)
        
    print(f"🎯 AI DECISION: Targeting {target_file} for remediation.")

    # Read the content of the target file
    with open(target_file, 'r') as f:
        original_code = f.read()

    # 4. REMEDIATION LOOP
    success = False
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"\n🔄 ATTEMPT {attempt}/{MAX_RETRIES}...")
        
        # --- MEMORY CHECK ---
        print("🔍 MEMORY: Searching for similar past experiences...")
        past_remedy = memory.recall(log_content)
        
        if past_remedy:
            print("💡 EUREKA: I found a highly similar error in my history!")
            diagnosis_to_use = f"RECALLED REMEDY: {past_remedy}"
            context = "" # Skip context fetching if we already know the answer
        else:
            # STAGE 1: Preliminary Diagnosis from scratch
            print("🧠 STAGE 1: No memory found. Analyzing error from scratch...")
            initial_diagnosis = get_diagnosis(original_code, log_content, "")
            
            # JIT Context Fetching (Passes diagnosis as the search key)
            context = get_supporting_context(target_file, initial_diagnosis, original_code)
            diagnosis_to_use = initial_diagnosis
            
            if context:
                print("🧠 STAGE 1.5: Refining diagnosis with discovered context...")
                diagnosis_to_use = get_diagnosis(original_code, log_content, context)
        
        print(f"\n🗣️ AI DIAGNOSIS:\n{diagnosis_to_use}\n")

        if "API Error:" in diagnosis_to_use:
            print("💀 ERROR: LLM Timeout. Retrying...")
            continue

        # STAGE 2: Code Generation
        print(f"🛠️ STAGE 2: Generating full rewrite for {target_file}...")
        raw_response = get_fixed_code(target_file, original_code, diagnosis_to_use, context)
        
        code_block_match = re.search(r"`{3}(?:[a-zA-Z0-9_+-]+)?\n(.*?)\n`{3}", raw_response, re.DOTALL)
        
        if code_block_match:
            fixed_code = code_block_match.group(1).strip()
            with open(target_file, 'w') as f:
                f.write(fixed_code)
                
            # STAGE 3: Verification (using the file-specific verification)
            verified, errors = verify_fix(target_file)
            if verified:
                print(f"✅ SUCCESS: {target_file} fixed and verified!")
                
                # 1. Commit to Long-Term Memory!
                if not past_remedy:
                    memory.learn(log_content, target_file, diagnosis_to_use)
                
                # 2. Push the code
                create_pull_request(diagnosis_to_use, target_file, attempt)
                
                # 3. Tell the team via Slack/Discord Webhook
                notify_team(target_file, diagnosis_to_use, attempt)
                
                success = True
                break
            else:
                print(f"❌ FAIL: Fix did not compile. Compiler said:\n{errors}")
                with open(target_file, 'w') as f:
                    f.write(original_code) # Revert for next try
        else:
            print("❌ ERROR: AI failed to provide a valid code block.")

    if not success:
        print("💀 ALL ATTEMPTS FAILED. Human intervention required.")
    print("="*50)