#!/usr/bin/env python3
import os
import sys
import re
import json
import sqlite3
import hashlib
import subprocess
import urllib.request
import urllib.parse
from datetime import datetime

# Reconfigure standard streams to UTF-8 on Windows to prevent UnicodeEncodeError when printing special characters
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, IOError):
        pass

# ============================================================================
# Antigravity Memory System (AMS) CLI
# ============================================================================

DB_DIR = os.path.join(os.getcwd(), ".agents")
DB_PATH = os.path.join(DB_DIR, "ams.db")
ENV_PATH = os.path.join(os.getcwd(), ".env")

# Ignore patterns for codebase scanning
IGNORE_DIRS = {
    "node_modules", ".git", "dist", "build", "out", "android-app",
    "storage", "chrome-profile", "graphify-out", ".agents",
    ".firebase", ".gemini", "public"
}
IGNORE_FILES = {
    "package-lock.json", "bun.lockb", "ams.db", "yarn.lock", "pnpm-lock.yaml"
}
ALLOWED_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".sql", ".md", ".json", ".html", ".css"
}

# ============================================================================
# DB Schema & Initialization
# ============================================================================

def init_db():
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Enable foreign keys
    cursor.execute("PRAGMA foreign_keys = ON;")

    # 1. codebase_files
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS codebase_files (
        file_path TEXT PRIMARY KEY,
        file_hash TEXT NOT NULL,
        last_modified INTEGER NOT NULL,
        is_ignored BOOLEAN NOT NULL DEFAULT 0
    );
    """)

    # 2. codebase_chunks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS codebase_chunks (
        id TEXT PRIMARY KEY,
        file_path TEXT NOT NULL REFERENCES codebase_files(file_path) ON DELETE CASCADE,
        chunk_type TEXT NOT NULL,
        symbol_name TEXT,
        content TEXT NOT NULL,
        start_line INTEGER NOT NULL,
        end_line INTEGER NOT NULL,
        chunk_hash TEXT NOT NULL,
        created_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
    );
    """)

    # 3. codebase_embeddings (simulated vec storage since vec0 might not be loaded)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS codebase_embeddings (
        chunk_id TEXT PRIMARY KEY REFERENCES codebase_chunks(id) ON DELETE CASCADE,
        embedding BLOB NOT NULL
    );
    """)

    # 4. FTS5 Virtual Table for full-text search
    try:
        cursor.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS codebase_fts USING fts5(
            chunk_id UNINDEXED,
            content,
            symbol_name
        );
        """)
    except sqlite3.OperationalError as e:
        # Fallback if FTS5 is not compiled in SQLite
        print(f"[-] Warning: FTS5 not supported in this SQLite build ({e}). Creating standard index fallback.")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS codebase_fts_fallback (
            chunk_id TEXT PRIMARY KEY REFERENCES codebase_chunks(id) ON DELETE CASCADE,
            content TEXT,
            symbol_name TEXT
        );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fts_fallback_content ON codebase_fts_fallback(content);")

    # 5. short_term_memory
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS short_term_memory (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at INTEGER NOT NULL DEFAULT (strftime('%s','now'))
    );
    """)

    # 6. system_config (tracks last sync commit, etc)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()
    print(f"[+] Database initialized at {DB_PATH}")


# ============================================================================
# API Keys & Embedding Client
# ============================================================================

def load_env_keys():
    keys = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("=", 1)
                if len(parts) == 2:
                    k = parts[0].strip()
                    v = parts[1].strip().strip('"').strip("'")
                    keys[k] = v
    # Merge with system environment
    for k, v in os.environ.items():
        keys[k] = v
    return keys

def get_embedding(text: str, keys: dict) -> list:
    """Fetch vector embeddings via OpenAI, Gemini, or Ollama."""
    # 1. Gemini API
    gemini_key = keys.get("GEMINI_API_KEY") or keys.get("VITE_GEMINI_API_KEY")
    if gemini_key:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={gemini_key}"
        data = {
            "content": {
                "parts": [{"text": text}]
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["embedding"]["values"]
        except Exception as e:
            # Fallback
            pass

    # 2. OpenAI API
    openai_key = keys.get("OPENAI_API_KEY")
    if openai_key:
        url = "https://api.openai.com/v1/embeddings"
        data = {
            "input": text,
            "model": "text-embedding-3-small"
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {openai_key}"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["data"][0]["embedding"]
        except Exception as e:
            pass

    # 3. Ollama (Local)
    ollama_host = keys.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_model = keys.get("OLLAMA_MODEL", "all-minilm")
    if ollama_host:
        url = f"{ollama_host}/api/embeddings"
        data = {
            "model": ollama_model,
            "prompt": text
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                res = json.loads(response.read().decode("utf-8"))
                return res["embedding"]
        except Exception:
            pass

    return [] # Return empty list if no client succeeded

def encode_vector(vector: list) -> bytes:
    """Store float array as binary BLOB for SQLite."""
    import array
    return array.array('f', vector).tobytes()

def decode_vector(blob: bytes) -> list:
    """Decode binary BLOB back to float array."""
    import array
    a = array.array('f')
    a.frombytes(blob)
    return a.tolist()

# ============================================================================
# AST-Based Chunkers
# ============================================================================

def chunk_javascript_typescript(file_path: str, content: str) -> list:
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    brace_count = 0
    in_block = False
    start_line = 0
    symbol_name = ""
    chunk_type = "general"

    func_pattern = re.compile(
        r'(?:export\s+|async\s+)*function\s+(\w+)|'
        r'(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>|'
        r'class\s+(\w+)'
    )

    for idx, line in enumerate(lines):
        line_num = idx + 1
        
        if not in_block:
            match = func_pattern.search(line)
            if match:
                in_block = True
                start_line = line_num
                current_chunk = [line]
                brace_count = line.count('{') - line.count('}')
                symbol_name = next(g for g in match.groups() if g is not None)
                chunk_type = 'class' if 'class' in line else 'function'
                
                if brace_count == 0 and '{' in line:
                    chunks.append({
                        'id': f"{file_path}#L{start_line}-{line_num}",
                        'content': '\n'.join(current_chunk),
                        'start_line': start_line,
                        'end_line': line_num,
                        'symbol_name': symbol_name,
                        'chunk_type': chunk_type
                    })
                    in_block = False
                    current_chunk = []
            else:
                current_chunk.append(line)
                if len(current_chunk) >= 45:
                    chunks.append({
                        'id': f"{file_path}#L{line_num - len(current_chunk) + 1}-{line_num}",
                        'content': '\n'.join(current_chunk),
                        'start_line': line_num - len(current_chunk) + 1,
                        'end_line': line_num,
                        'symbol_name': None,
                        'chunk_type': 'general'
                    })
                    current_chunk = current_chunk[-10:] # sliding overlap
        else:
            current_chunk.append(line)
            brace_count += line.count('{') - line.count('}')
            if brace_count <= 0:
                chunks.append({
                    'id': f"{file_path}#L{start_line}-{line_num}",
                    'content': '\n'.join(current_chunk),
                    'start_line': start_line,
                    'end_line': line_num,
                    'symbol_name': symbol_name,
                    'chunk_type': chunk_type
                })
                in_block = False
                current_chunk = []
                brace_count = 0
                
    if current_chunk:
        chunks.append({
            'id': f"{file_path}#L{len(lines) - len(current_chunk) + 1}-{len(lines)}",
            'content': '\n'.join(current_chunk),
            'start_line': len(lines) - len(current_chunk) + 1,
            'end_line': len(lines),
            'symbol_name': None,
            'chunk_type': 'general'
        })
    return chunks

def chunk_python(file_path: str, content: str) -> list:
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    in_block = False
    start_indent = 0
    start_line = 0
    symbol_name = ""
    chunk_type = "general"

    func_pattern = re.compile(r'^\s*(def|class)\s+(\w+)')

    for idx, line in enumerate(lines):
        line_num = idx + 1
        stripped = line.strip()
        if not stripped:
            if in_block:
                current_chunk.append(line)
            continue
            
        indent = len(line) - len(line.lstrip())
        
        if not in_block:
            match = func_pattern.search(line)
            if match:
                in_block = True
                start_line = line_num
                start_indent = indent
                current_chunk = [line]
                symbol_name = match.group(2)
                chunk_type = 'class' if match.group(1) == 'class' else 'function'
            else:
                current_chunk.append(line)
                if len(current_chunk) >= 45:
                    chunks.append({
                        'id': f"{file_path}#L{line_num - len(current_chunk) + 1}-{line_num}",
                        'content': '\n'.join(current_chunk),
                        'start_line': line_num - len(current_chunk) + 1,
                        'end_line': line_num,
                        'symbol_name': None,
                        'chunk_type': 'general'
                    })
                    current_chunk = current_chunk[-10:]
        else:
            if indent <= start_indent and not stripped.startswith(('def ', 'class ', '#')):
                chunks.append({
                    'id': f"{file_path}#L{start_line}-{line_num-1}",
                    'content': '\n'.join(current_chunk),
                    'start_line': start_line,
                    'end_line': line_num - 1,
                    'symbol_name': symbol_name,
                    'chunk_type': chunk_type
                })
                # Assess if this line is the start of a next block
                match = func_pattern.search(line)
                if match:
                    start_line = line_num
                    start_indent = indent
                    current_chunk = [line]
                    symbol_name = match.group(2)
                    chunk_type = 'class' if match.group(1) == 'class' else 'function'
                else:
                    in_block = False
                    current_chunk = [line]
            else:
                current_chunk.append(line)
                
    if in_block and current_chunk:
        chunks.append({
            'id': f"{file_path}#L{start_line}-{len(lines)}",
            'content': '\n'.join(current_chunk),
            'start_line': start_line,
            'end_line': len(lines),
            'symbol_name': symbol_name,
            'chunk_type': chunk_type
        })
    elif current_chunk:
        chunks.append({
            'id': f"{file_path}#L{len(lines) - len(current_chunk) + 1}-{len(lines)}",
            'content': '\n'.join(current_chunk),
            'start_line': len(lines) - len(current_chunk) + 1,
            'end_line': len(lines),
            'symbol_name': None,
            'chunk_type': 'general'
        })
    return chunks

def chunk_sql(file_path: str, content: str) -> list:
    # SQL files are split by commands delimited by semicolon
    statements = content.split(";")
    chunks = []
    line_offset = 1
    
    for idx, stmt in enumerate(statements):
        stmt_stripped = stmt.strip()
        if not stmt_stripped:
            continue
            
        stmt_lines = stmt.split("\n")
        start_line = line_offset
        end_line = line_offset + len(stmt_lines) - 1
        line_offset = end_line + 1
        
        # Pull out symbol name e.g. table name or function name
        symbol_name = None
        chunk_type = "general"
        create_match = re.search(r'CREATE\s+(?:OR\s+REPLACE\s+)?(TABLE|FUNCTION|TRIGGER|INDEX)\s+(?:IF\s+NOT\s+EXISTS\s+)?([\w\.]+)', stmt_stripped, re.IGNORECASE)
        if create_match:
            chunk_type = create_match.group(1).lower()
            symbol_name = create_match.group(2)
            
        chunks.append({
            'id': f"{file_path}#S{idx+1}",
            'content': stmt_stripped + ";",
            'start_line': start_line,
            'end_line': end_line,
            'symbol_name': symbol_name,
            'chunk_type': chunk_type
        })
    return chunks

def chunk_markdown(file_path: str, content: str) -> list:
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    header_name = None
    start_line = 1
    
    for idx, line in enumerate(lines):
        line_num = idx + 1
        if line.startswith(('#', '##', '###', '####')):
            # Flush existing chunk
            if current_chunk:
                chunks.append({
                    'id': f"{file_path}#L{start_line}-{line_num-1}",
                    'content': '\n'.join(current_chunk),
                    'start_line': start_line,
                    'end_line': line_num - 1,
                    'symbol_name': header_name,
                    'chunk_type': 'markdown_section'
                })
            start_line = line_num
            current_chunk = [line]
            header_name = line.lstrip('#').strip()
        else:
            current_chunk.append(line)
            
    if current_chunk:
        chunks.append({
            'id': f"{file_path}#L{start_line}-{len(lines)}",
            'content': '\n'.join(current_chunk),
            'start_line': start_line,
            'end_line': len(lines),
            'symbol_name': header_name,
            'chunk_type': 'markdown_section'
        })
    return chunks

def chunk_generic(file_path: str, content: str) -> list:
    lines = content.split('\n')
    chunks = []
    current_chunk = []
    
    for idx, line in enumerate(lines):
        line_num = idx + 1
        current_chunk.append(line)
        if len(current_chunk) >= 50:
            chunks.append({
                'id': f"{file_path}#L{line_num - len(current_chunk) + 1}-{line_num}",
                'content': '\n'.join(current_chunk),
                'start_line': line_num - len(current_chunk) + 1,
                'end_line': line_num,
                'symbol_name': None,
                'chunk_type': 'general'
            })
            current_chunk = current_chunk[-10:] # overlap
            
    if current_chunk:
        chunks.append({
            'id': f"{file_path}#L{len(lines) - len(current_chunk) + 1}-{len(lines)}",
            'content': '\n'.join(current_chunk),
            'start_line': len(lines) - len(current_chunk) + 1,
            'end_line': len(lines),
            'symbol_name': None,
            'chunk_type': 'general'
        })
    return chunks

def chunk_file(file_path: str, content: str) -> list:
    ext = os.path.splitext(file_path)[1].lower()
    if ext in {".ts", ".tsx", ".js", ".jsx"}:
        return chunk_javascript_typescript(file_path, content)
    elif ext == ".py":
        return chunk_python(file_path, content)
    elif ext == ".sql":
        return chunk_sql(file_path, content)
    elif ext == ".md":
        return chunk_markdown(file_path, content)
    else:
        return chunk_generic(file_path, content)

# ============================================================================
# Git-Diff Sync Logic
# ============================================================================

def compute_file_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()

def should_ignore(path: str) -> bool:
    path_norm = path.replace("\\", "/")
    parts = path_norm.split("/")
    for p in parts:
        if p in IGNORE_DIRS:
            return True
    filename = os.path.basename(path_norm)
    if filename in IGNORE_FILES:
        return True
    ext = os.path.splitext(path_norm)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return True
    return False

def get_git_status():
    """Runs git rev-parse HEAD to fetch active commit SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True
        )
        return res.stdout.decode("utf-8").strip()
    except subprocess.SubprocessError:
        return None

def scan_repository_cold_start() -> list:
    """Scans all non-ignored files in the repository (Cold Start)."""
    tracked_files = []
    for root, dirs, files in os.walk(os.getcwd()):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, os.getcwd())
            if should_ignore(rel_path):
                continue
            tracked_files.append(rel_path)
    return tracked_files

def run_sync(force: bool = False):
    if not os.path.exists(DB_PATH):
        init_db()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load API keys
    keys = load_env_keys()
    has_embeddings = bool(keys.get("GEMINI_API_KEY") or keys.get("VITE_GEMINI_API_KEY") or keys.get("OPENAI_API_KEY"))
    if not has_embeddings:
        print("[!] No OpenAI or Gemini API Keys detected in environment. Falling back to pure BM25 Lexical search (FTS5).")

    # Fetch last sync git SHA
    cursor.execute("SELECT value FROM system_config WHERE key = 'last_sync_commit';")
    row = cursor.fetchone()
    last_sha = row[0] if row else None
    current_sha = get_git_status()

    files_to_sync = []
    files_to_delete = []

    if force or not last_sha or not current_sha:
        print("[*] Performing full repository scan (Cold Start)...")
        files_to_sync = scan_repository_cold_start()
    else:
        print(f"[*] Detecting changes since last sync ({last_sha[:7]} -> {current_sha[:7]})...")
        try:
            # git diff --name-status
            diff_res = subprocess.run(
                ["git", "diff", "--name-status", last_sha, "HEAD"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )
            lines = diff_res.stdout.decode("utf-8").strip().split("\n")
            for line in lines:
                if not line.strip():
                    continue
                parts = line.split(maxsplit=1)
                if len(parts) < 2:
                    continue
                status, rel_path = parts[0], parts[1].strip()
                if should_ignore(rel_path):
                    continue
                if status == 'D':
                    files_to_delete.append(rel_path)
                else: # A (Added) or M (Modified)
                    files_to_sync.append(rel_path)
        except subprocess.SubprocessError as diff_err:
            print(f"[-] Git diff failed ({diff_err}). Falling back to full scan.")
            files_to_sync = scan_repository_cold_start()

    # Delete removed files from DB
    if files_to_delete:
        print(f"[*] Deleting records for {len(files_to_delete)} removed files...")
        for f in files_to_delete:
            cursor.execute("DELETE FROM codebase_files WHERE file_path = ?;", (f,))
        conn.commit()

    # Sync modified & added files
    total_added = 0
    total_updated = 0
    api_calls = 0

    print(f"[*] Processing {len(files_to_sync)} files...")
    for file_path in files_to_sync:
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except IOError as io_err:
            print(f"[-] Skip {file_path}: {io_err}")
            continue

        file_hash = compute_file_hash(content)
        mtime = int(os.path.getmtime(file_path))

        # Check if hash changed in DB
        cursor.execute("SELECT file_hash FROM codebase_files WHERE file_path = ?;", (file_path,))
        db_row = cursor.fetchone()
        
        if db_row and db_row[0] == file_hash:
            # File is unchanged, skip parsing
            continue

        if db_row:
            total_updated += 1
            # Purge old file chunks to replace incrementally (cascade deletes chunks and embeddings)
            cursor.execute("DELETE FROM codebase_files WHERE file_path = ?;", (file_path,))
        else:
            total_added += 1

        # Save file metadata
        cursor.execute("INSERT OR REPLACE INTO codebase_files (file_path, file_hash, last_modified) VALUES (?, ?, ?);",
                       (file_path, file_hash, mtime))

        # Chunk content
        chunks = chunk_file(file_path, content)
        for chunk in chunks:
            chunk_hash = compute_file_hash(chunk["content"])
            chunk_id = chunk["id"]

            # Save chunk metadata
            cursor.execute(
                "INSERT OR REPLACE INTO codebase_chunks (id, file_path, chunk_type, symbol_name, content, start_line, end_line, chunk_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                (chunk_id, file_path, chunk["chunk_type"], chunk["symbol_name"], chunk["content"], chunk["start_line"], chunk["end_line"], chunk_hash)
            )

            # Save Lexical full-text index
            try:
                cursor.execute(
                    "INSERT OR REPLACE INTO codebase_fts (chunk_id, content, symbol_name) VALUES (?, ?, ?);",
                    (chunk_id, chunk["content"], chunk["symbol_name"])
                )
            except sqlite3.OperationalError:
                # FTS Fallback
                cursor.execute(
                    "INSERT OR REPLACE INTO codebase_fts_fallback (chunk_id, content, symbol_name) VALUES (?, ?, ?);",
                    (chunk_id, chunk["content"], chunk["symbol_name"])
                )

            # Generate and save Embeddings (if keys available)
            if has_embeddings:
                vector = get_embedding(chunk["content"], keys)
                if vector:
                    api_calls += 1
                    cursor.execute(
                        "INSERT OR REPLACE INTO codebase_embeddings (chunk_id, embedding) VALUES (?, ?);",
                        (chunk_id, encode_vector(vector))
                    )

        conn.commit()

    # Record sync SHA
    if current_sha:
        cursor.execute("INSERT OR REPLACE INTO system_config (key, value) VALUES ('last_sync_commit', ?);", (current_sha,))
        conn.commit()

    conn.close()
    print(f"[+] Sync completed. Files Added: {total_added}, Updated: {total_updated}, API Embedding Calls: {api_calls}")


# ============================================================================
# Retrieval & Querying (Hybrid Rerank)
# ============================================================================

def cosine_similarity(v1: list, v2: list) -> float:
    import numpy as np
    a = np.array(v1)
    b = np.array(v2)
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot / (norm_a * norm_b))

def run_query(query_text: str):
    if not os.path.exists(DB_PATH):
        print("[-] Database not synchronized. Please run `sync` first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Load keys for query embedding
    keys = load_env_keys()
    has_embeddings = bool(keys.get("GEMINI_API_KEY") or keys.get("VITE_GEMINI_API_KEY") or keys.get("OPENAI_API_KEY"))

    try:
        # FTS5 match query
        cursor.execute("""
            SELECT chunk_id, symbol_name, content 
            FROM codebase_fts 
            WHERE codebase_fts MATCH ? 
            LIMIT 40;
        """, (query_text,))
        lexical_results = cursor.fetchall()
    except sqlite3.OperationalError:
        # Fallback query using LIKE on codebase_chunks directly (which always exists)
        cursor.execute("""
            SELECT id, symbol_name, content 
            FROM codebase_chunks 
            WHERE content LIKE ? OR symbol_name LIKE ?
            LIMIT 40;
        """, (f"%{query_text}%", f"%{query_text}%"))
        lexical_results = cursor.fetchall()

    # Rank lexical results
    lexical_scores = {row[0]: (idx + 1) for idx, row in enumerate(lexical_results)} # rank position

    # 2. Fetch Semantic candidates (if embeddings configured)
    semantic_scores = {}
    if has_embeddings:
        query_vec = get_embedding(query_text, keys)
        if query_vec:
            cursor.execute("SELECT chunk_id, embedding FROM codebase_embeddings;")
            all_embeddings = cursor.fetchall()
            
            similarities = []
            for chunk_id, vec_blob in all_embeddings:
                vec = decode_vector(vec_blob)
                sim = cosine_similarity(query_vec, vec)
                similarities.append((chunk_id, sim))
            
            # Sort by similarity descending
            similarities.sort(key=lambda x: x[1], reverse=True)
            for rank_idx, (chunk_id, sim) in enumerate(similarities[:40]):
                semantic_scores[chunk_id] = rank_idx + 1

    # 3. Reciprocal Rank Fusion (RRF) Rerank
    # RRF = 1 / (Rank_Lexical + 60) + 1 / (Rank_Semantic + 60)
    scores = {}
    
    # Retrieve all unique candidate details
    candidate_ids = set(lexical_scores.keys()).union(semantic_scores.keys())
    if not candidate_ids:
        print("[*] No matching files found.")
        conn.close()
        return

    placeholders = ",".join("?" for _ in candidate_ids)
    cursor.execute(f"""
        SELECT id, file_path, chunk_type, symbol_name, content, start_line, end_line 
        FROM codebase_chunks 
        WHERE id IN ({placeholders});
    """, list(candidate_ids))
    candidates = cursor.fetchall()

    for cand in candidates:
        chunk_id = cand[0]
        rank_lex = lexical_scores.get(chunk_id, 999)
        rank_sem = semantic_scores.get(chunk_id, 999)
        
        score_lex = 1.0 / (rank_lex + 60.0)
        score_sem = 1.0 / (rank_sem + 60.0)
        
        # Weighted higher on semantic if available
        scores[chunk_id] = score_lex + (score_sem if has_embeddings else 0)

    # Sort candidates by combined score
    ranked_chunks = sorted(candidates, key=lambda x: scores.get(x[0], 0), reverse=True)

    # Print results
    print(f"\n[+] Found {len(ranked_chunks)} matching results for query: '{query_text}'\n" + "-"*80)
    for idx, cand in enumerate(ranked_chunks[:5]):
        chunk_id, file_path, chunk_type, symbol, content, start, end = cand
        print(f"\n{idx+1}. File: {file_path} (Lines {start}-{end}) | Type: {chunk_type} | Symbol: {symbol or 'None'}")
        print("-" * 40)
        
        # Print snippet with line offsets
        snippet_lines = content.split("\n")
        for line_idx, line in enumerate(snippet_lines[:15]):
            print(f"{start + line_idx:4d} | {line}")
        if len(snippet_lines) > 15:
            print("     | ... (truncated)")
        print("-" * 80)

    conn.close()

# ============================================================================
# Power Extensions: RPC Lookup, Short-Term Memory & Compaction
# ============================================================================

def run_rpc(rpc_name: str):
    """Searches indexed SQL chunks for RPC function definitions matching rpc_name."""
    if not os.path.exists(DB_PATH):
        print("[-] Database does not exist. Run init first.")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    pattern = f"%{rpc_name}%"
    cursor.execute("""
        SELECT file_path, start_line, end_line, symbol_name, content
        FROM codebase_chunks
        WHERE (file_path LIKE '%.sql' OR file_path LIKE '%.ts' OR file_path LIKE '%.tsx')
          AND (content LIKE ? OR symbol_name LIKE ?)
        ORDER BY start_line ASC LIMIT 5;
    """, (pattern, pattern))
    rows = cursor.fetchall()
    if not rows:
        print(f"[*] No RPC references found for '{rpc_name}'.")
    else:
        print(f"\n[+] Found {len(rows)} RPC references for: '{rpc_name}'\n" + "-"*80)
        for idx, (path, start, end, symbol, content) in enumerate(rows):
            print(f"{idx+1}. File: {path} (Lines {start}-{end}) | Symbol: {symbol or 'None'}")
            print("-" * 40)
            lines = content.split("\n")
            for line_idx, line in enumerate(lines[:12]):
                print(f"{start + line_idx:4d} | {line}")
            if len(lines) > 12:
                print("     | ... (truncated)")
            print("-" * 80)
    conn.close()

def run_remember(key: str, value: str):
    """Saves a key-value fact into AMS short-term memory."""
    if not os.path.exists(DB_PATH):
        init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO short_term_memory (key, value, updated_at) VALUES (?, ?, strftime('%s','now'));", (key, value))
    conn.commit()
    conn.close()
    print(f"[+] AMS Memory Saved: [{key}] => {value}")

def run_recall(key: str = None):
    """Recalls saved key-value facts from AMS short-term memory."""
    if not os.path.exists(DB_PATH):
        print("[-] Memory empty. Run init first.")
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if key:
        cursor.execute("SELECT key, value, updated_at FROM short_term_memory WHERE key LIKE ? ORDER BY updated_at DESC;", (f"%{key}%",))
    else:
        cursor.execute("SELECT key, value, updated_at FROM short_term_memory ORDER BY updated_at DESC LIMIT 20;")
    rows = cursor.fetchall()
    if not rows:
        print("[-] No matching facts found in AMS memory.")
    else:
        print("\n--- Antigravity Memory System (AMS) Recall ---")
        for k, val, ts in rows:
            print(f"• [{k}]: {val}")
        print("----------------------------------------------\n")
    conn.close()

def run_compact():
    """Compacts the SQLite database, removing orphan chunks and running VACUUM."""
    if not os.path.exists(DB_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM codebase_chunks WHERE file_path NOT IN (SELECT file_path FROM codebase_files);")
    conn.commit()
    cursor.execute("VACUUM;")
    conn.close()
    print("[+] AMS Database compacted successfully.")

# ============================================================================
# Status & Stats
# ============================================================================

def run_status():
    if not os.path.exists(DB_PATH):
        print("[-] Database does not exist. Run init first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM codebase_files;")
    files_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM codebase_chunks;")
    chunks_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM codebase_embeddings;")
    embeddings_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM short_term_memory;")
    memory_count = cursor.fetchone()[0]

    cursor.execute("SELECT value FROM system_config WHERE key = 'last_sync_commit';")
    row = cursor.fetchone()
    last_sha = row[0] if row else "Never Synced"

    db_size = os.path.getsize(DB_PATH) / (1024 * 1024) # MB

    print("\n--- Antigravity Memory System (AMS) Status ---")
    print(f"Database Path:      {DB_PATH}")
    print(f"Database Size:      {db_size:.2f} MB")
    print(f"Last Synced Git:    {last_sha}")
    print(f"Files Indexed:      {files_count}")
    print(f"Total Chunks:       {chunks_count}")
    print(f"Memory Items:       {memory_count}")
    print(f"Vector Embeddings:  {embeddings_count} / {chunks_count}")
    print("----------------------------------------------\n")
    conn.close()

# ============================================================================
# CLI Command router
# ============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python ams.py [init|sync|query|rpc|remember|recall|compact|status] [args]")
        print("Commands:")
        print("  init            Initializes the local SQLite database")
        print("  sync [--force]  Synchronizes changes from Git repository incrementally")
        print("  query <text>    Queries indexed files using hybrid BM25 + semantic similarity")
        print("  rpc <name>      Searches indexed RPC functions and database queries")
        print("  remember <k> <v>Stores a project fact into AMS short-term memory")
        print("  recall [key]    Recalls stored project facts from AMS memory")
        print("  compact         Compacts SQLite database and vacuoms storage")
        print("  status          Displays database and index statistics")
        sys.exit(1)

    cmd = sys.argv[1].lower()

    if cmd == "init":
        init_db()
    elif cmd == "sync":
        force = "--force" in sys.argv
        run_sync(force=force)
    elif cmd == "query":
        if len(sys.argv) < 3:
            print("Error: Missing query string. Usage: python ams.py query 'search query'")
            sys.exit(1)
        run_query(sys.argv[2])
    elif cmd == "rpc":
        if len(sys.argv) < 3:
            print("Error: Missing RPC name. Usage: python ams.py rpc 'get_available_vehicles'")
            sys.exit(1)
        run_rpc(sys.argv[2])
    elif cmd == "remember":
        if len(sys.argv) < 4:
            print("Error: Usage: python ams.py remember 'key' 'value'")
            sys.exit(1)
        run_remember(sys.argv[2], sys.argv[3])
    elif cmd == "recall":
        key = sys.argv[2] if len(sys.argv) >= 3 else None
        run_recall(key)
    elif cmd == "compact":
        run_compact()
    elif cmd == "status":
        run_status()
    else:
        print(f"[-] Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
