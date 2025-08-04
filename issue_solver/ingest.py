# ingest_repo.py

import os
import time
import argparse
import subprocess
import shutil
import ast
import re
from typing import List, Dict, Any

from dotenv import load_dotenv
from github import Github, RateLimitExceededException
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from tqdm import tqdm

# --- CONFIGURATION ---
# Load environment variables from .env file
load_dotenv()

# Gemini model details. The 'embedding-001' is a powerful free model.
# Its output vectors have 768 dimensions.
GEMINI_EMBEDDING_MODEL = "models/embedding-001"

# Chroma configuration
#CHROMA_PERSIST_DIR = "chroma_db"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PERSIST_DIR = os.path.join(PROJECT_ROOT, "chroma_db")

# Collection configuration (replaces Pinecone namespaces)
COLLECTION_ISSUES = "issues_history"
COLLECTION_DOCS = "documentation"
COLLECTION_PR_HISTORY = "pr_history"
COLLECTION_REPO_CODE = "repo_code_main"

def extract_functions_from_code(file_content: str, file_path: str) -> List[Dict[str, Any]]:
    """Extract individual functions from code files."""
    functions = []
    file_ext = os.path.splitext(file_path)[1].lower()
    
    try:
        if file_ext in ['.py']:
            # Parse Python files using AST
            tree = ast.parse(file_content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_line = node.lineno
                    # Get the function/class code
                    lines = file_content.split('\n')
                    
                    # Find the end of the function/class by looking at indentation
                    end_line = len(lines)
                    base_indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
                    
                    for i in range(start_line, len(lines)):
                        line = lines[i]
                        if line.strip() and len(line) - len(line.lstrip()) <= base_indent and i > start_line:
                            end_line = i
                            break
                    
                    func_code = '\n'.join(lines[start_line-1:end_line])
                    functions.append({
                        "name": node.name,
                        "type": "class" if isinstance(node, ast.ClassDef) else "function",
                        "code": func_code,
                        "start_line": start_line,
                        "end_line": end_line
                    })
        
        elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
            # Simple regex-based function extraction for JavaScript/TypeScript
            # This is a basic implementation - could be improved with proper parsing
            function_patterns = [
                r'(function\s+\w+\s*\([^)]*\)\s*\{)',  # function declarations
                r'(const\s+\w+\s*=\s*\([^)]*\)\s*=>\s*\{)',  # arrow functions
                r'(\w+\s*:\s*function\s*\([^)]*\)\s*\{)',  # object methods
                r'(\w+\s*\([^)]*\)\s*\{)',  # method definitions
            ]
            
            for pattern in function_patterns:
                matches = re.finditer(pattern, file_content, re.MULTILINE)
                for match in matches:
                    start_pos = match.start()
                    # Find the matching closing brace
                    brace_count = 0
                    end_pos = start_pos
                    for i, char in enumerate(file_content[start_pos:]):
                        if char == '{':
                            brace_count += 1
                        elif char == '}':
                            brace_count -= 1
                            if brace_count == 0:
                                end_pos = start_pos + i + 1
                                break
                    
                    func_code = file_content[start_pos:end_pos]
                    func_name = re.search(r'(?:function\s+|const\s+|)(\w+)', func_code)
                    func_name = func_name.group(1) if func_name else "anonymous"
                    
                    functions.append({
                        "name": func_name,
                        "type": "function",
                        "code": func_code,
                        "start_line": file_content[:start_pos].count('\n') + 1,
                        "end_line": file_content[:end_pos].count('\n') + 1
                    })
        
        # If no functions found or for other file types, return the whole file
        if not functions:
            functions.append({
                "name": os.path.basename(file_path),
                "type": "file",
                "code": file_content,
                "start_line": 1,
                "end_line": file_content.count('\n') + 1
            })
            
    except Exception as e:
        print(f"Error parsing functions from {file_path}: {e}")
        # Fallback to whole file
        functions.append({
            "name": os.path.basename(file_path),
            "type": "file", 
            "code": file_content,
            "start_line": 1,
            "end_line": file_content.count('\n') + 1
        })
    
    return functions

def fetch_repo_code(repo_full_name: str):
    """
    Clones the repository and extracts code files with function-level chunking.
    """
    print("Cloning repository for code analysis...")
    temp_dir = f"./temp_clone_{repo_full_name.replace('/', '_')}"
    
    # Remove the directory if it exists from a previous failed run
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        
    # Construct the clone URL with the token for private repos
    github_token = os.getenv("GITHUB_TOKEN")
    clone_url = f"https://{github_token}@github.com/{repo_full_name}.git"
    
    try:
        # Use subprocess to run the git clone command
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone repository: {e.stderr}")
        # Attempt to clone without token for public repos if the above failed
        try:
            clone_url = f"https://github.com/{repo_full_name}.git"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, temp_dir],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e2:
            print(f"Failed to clone public repository: {e2.stderr}")
            shutil.rmtree(temp_dir)
            return []

    print("Extracting code files from local clone...")
    code_chunks = []
    
    # Define code file extensions
    code_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift']
    
    # Use os.walk to efficiently traverse the local directory
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if any(file.endswith(ext) for ext in code_extensions):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Get the relative path to use as the source identifier
                    relative_path = os.path.relpath(file_path, temp_dir)
                    
                    # Extract functions from the file
                    functions = extract_functions_from_code(content, relative_path)
                    
                    for func in functions:
                        code_chunks.append({
                            "source": relative_path,
                            "content": func["code"],
                            "type": "code",
                            "filePath": relative_path,
                            "functionName": func["name"],
                            "functionType": func["type"],
                            "branch": "main",
                            "start_line": func["start_line"],
                            "end_line": func["end_line"]
                        })
                        
                except Exception as e:
                    print(f"Could not read file {file_path}: {e}")

    # Clean up the temporary directory
    shutil.rmtree(temp_dir)
    
    print(f"Found and processed {len(code_chunks)} code chunks.")
    return code_chunks

def fetch_repo_docs(repo_full_name: str):
    """
    Clones the repository to a temporary local directory and extracts all
    Markdown and text files. This is much faster than using the API for
    repositories with many files.
    """
    print("Cloning repository for faster file access...")
    temp_dir = f"./temp_clone_{repo_full_name.replace('/', '_')}"
    
    # Remove the directory if it exists from a previous failed run
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
        
    # Construct the clone URL with the token for private repos
    github_token = os.getenv("GITHUB_TOKEN")
    clone_url = f"https://{github_token}@github.com/{repo_full_name}.git"
    
    try:
        # Use subprocess to run the git clone command
        subprocess.run(
            ["git", "clone", "--depth", "1", clone_url, temp_dir],
            check=True,
            capture_output=True,
            text=True
        )
        print("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to clone repository: {e.stderr}")
        # Attempt to clone without token for public repos if the above failed
        try:
            clone_url = f"https://github.com/{repo_full_name}.git"
            subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, temp_dir],
                check=True,
                capture_output=True,
                text=True
            )
        except subprocess.CalledProcessError as e2:
            print(f"Failed to clone public repository: {e2.stderr}")
            shutil.rmtree(temp_dir) # Clean up
            return []


    print("Extracting documentation files (.md, .txt) from local clone...")
    docs = []
    # Use os.walk to efficiently traverse the local directory
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if file.endswith((".md", ".txt", "README")):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Get the relative path to use as the source identifier
                    relative_path = os.path.relpath(file_path, temp_dir)
                    docs.append({"source": relative_path, "content": content, "type": "doc"})
                except Exception as e:
                    print(f"Could not read file {file_path}: {e}")

    # Clean up the temporary directory
    shutil.rmtree(temp_dir)
    
    print(f"Found and processed {len(docs)} documentation files.")
    return docs

def fetch_repo_pr_history(repo):
    """Fetches merged pull request history with diffs."""
    print("Fetching pull request history...")
    pr_data = []
    
    try:
        # Get merged PRs (limit to recent ones to avoid rate limits)
        prs = repo.get_pulls(state="closed", sort="updated", direction="desc")
        
        count = 0
        for pr in tqdm(prs, desc="Fetching PR history"):
            if count >= 100:  # Limit to recent 100 PRs to avoid rate limits
                break
                
            if pr.merged:
                try:
                    # Get PR files and their diffs
                    files = pr.get_files()
                    pr_content = f"Title: {pr.title}\nDescription: {pr.body or 'No description'}\n\n"
                    
                    # Add file changes
                    for file in files:
                        if file.patch:  # Some files might not have patches (binary files, etc.)
                            pr_content += f"File: {file.filename}\nStatus: {file.status}\n"
                            pr_content += f"Diff:\n{file.patch}\n\n"
                    
                    pr_data.append({
                        "source": f"PR #{pr.number}",
                        "content": pr_content,
                        "type": "pr",
                        "pr_number": pr.number,
                        "pr_title": pr.title,
                        "pr_url": pr.html_url,
                        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None
                    })
                    count += 1
                    
                except Exception as e:
                    print(f"Error fetching PR #{pr.number}: {e}")
                    continue
                    
    except Exception as e:
        print(f"Error fetching PR history: {e}")
    
    print(f"Found {len(pr_data)} merged PRs.")
    return pr_data


# --- INITIALIZATION ---
def initialize_clients():
    """Initializes and returns clients for all required services."""
    try:
        # GitHub
        github_token = os.getenv("GITHUB_TOKEN")
        if not github_token:
            raise ValueError("GITHUB_TOKEN not found in .env file")
        g = Github(github_token)

        # Google AI (Gemini)
        google_api_key = os.getenv("GOOGLE_API_KEY")
        if not google_api_key:
            raise ValueError("GOOGLE_API_KEY not found in .env file")
        genai.configure(api_key=google_api_key)

        # Initialize embeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model=GEMINI_EMBEDDING_MODEL, 
            google_api_key=google_api_key
        )

        return g, embeddings
    except Exception as e:
        print(f"Error during client initialization: {e}")
        exit()

def create_chroma_collection(embeddings, collection_name: str):
    """Create or get a Chroma collection."""
    print(f"Creating/connecting to Chroma collection: {collection_name}")
    return Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=collection_name
    )

# --- DATA FETCHING ---
def fetch_repo_docs_api(repo):
    """Fetches all Markdown and text files from the repository using GitHub API."""
    print("Fetching documentation files (.md, .txt) from the repository...")
    docs = []
    contents = repo.get_contents("")
    while contents:
        file_content = contents.pop(0)
        if file_content.type == "dir":
            contents.extend(repo.get_contents(file_content.path))
        else:
            # We are interested in text-based docs
            if file_content.path.endswith((".md", ".txt", "README")):
                try:
                    content = file_content.decoded_content.decode("utf-8")
                    docs.append({"source": file_content.path, "content": content, "type": "doc"})
                except Exception as e:
                    print(f"Could not decode file {file_content.path}: {e}")
    print(f"Found {len(docs)} documentation files.")
    return docs

def fetch_repo_issues(repo):
    """Fetches all open and closed issues from the repository."""
    print("Fetching all issues (open and closed)...")
    issues_data = []
    issues = repo.get_issues(state="all")
    for issue in tqdm(issues, desc="Fetching issues"):
        # Combine title, body, and comments for a complete context
        comments_text = "\n".join([comment.body for comment in issue.get_comments()])
        full_issue_text = f"Title: {issue.title}\nBody: {issue.body}\nComments:\n{comments_text}"
        
        issues_data.append({
            "source": f"issue #{issue.number}",
            "content": full_issue_text,
            "type": "issue"
        })
    print(f"Found {len(issues_data)} issues.")
    return issues_data

# --- PROCESSING & UPSERTING ---
def chunk_and_embed_and_store(documents, embeddings, collection_name: str):
    """Chunks documents, creates embeddings, and stores in Chroma collection."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    
    batch_size = 100 # Process in batches to manage memory
    total_documents_stored = 0
    
    print(f"Processing {len(documents)} documents for collection '{collection_name}'...")
    
    # Create/get the Chroma collection
    chroma_collection = create_chroma_collection(embeddings, collection_name)
    
    for i in tqdm(range(0, len(documents), batch_size), desc=f"Processing {collection_name} in batches"):
        batch_docs = documents[i:i + batch_size]
        
        all_chunks = []
        all_metadatas = []
        
        # 1. Chunking and metadata preparation
        for doc in batch_docs:
            # For code documents, we might want to preserve the full function/class
            if doc.get("type") == "code" and len(doc["content"]) <= 2000:
                # Don't chunk small code blocks
                chunks = [doc["content"]]
            else:
                chunks = text_splitter.split_text(doc["content"])
            
            for j, chunk in enumerate(chunks):
                # Create enhanced metadata based on document type
                metadata = {
                    "source": doc["source"],
                    "type": doc["type"],
                    "collection_name": collection_name,
                    "chunk_index": j
                }
                
                # Add type-specific metadata
                if doc.get("type") == "code":
                    metadata.update({
                        "filePath": doc.get("filePath", ""),
                        "functionName": doc.get("functionName", ""),
                        "functionType": doc.get("functionType", ""),
                        "branch": doc.get("branch", "main"),
                        "start_line": doc.get("start_line"),
                        "end_line": doc.get("end_line")
                    })
                elif doc.get("type") == "pr":
                    metadata.update({
                        "pr_number": doc.get("pr_number"),
                        "pr_title": doc.get("pr_title", ""),
                        "pr_url": doc.get("pr_url", ""),
                        "merged_at": doc.get("merged_at")
                    })
                
                all_chunks.append(chunk)
                all_metadatas.append(metadata)
        
        if not all_chunks:
            continue

        # 2. Create Document objects for Chroma
        langchain_docs = [
            Document(page_content=chunk, metadata=metadata)
            for chunk, metadata in zip(all_chunks, all_metadatas)
        ]
        
        # 3. Add to Chroma collection in smaller sub-batches
        sub_batch_size = 50  # Smaller batches to avoid memory issues
        for start in range(0, len(langchain_docs), sub_batch_size):
            end = start + sub_batch_size
            sub_batch = langchain_docs[start:end]
            
            try:
                chroma_collection.add_documents(sub_batch)
                total_documents_stored += len(sub_batch)
            except Exception as e:
                print(f"Error adding batch to Chroma: {e}")
            continue
            
    # Note: Chroma automatically persists to disk when using persist_directory
    
    print(f"Finished {collection_name}. Total documents stored: {total_documents_stored}")
    return total_documents_stored


# --- MAIN EXECUTION ---
# The main execution block is removed to convert this file into a library module.
# The functionality will be invoked from the main server or a dedicated script.