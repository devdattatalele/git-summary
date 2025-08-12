# ingest_repo.py

import os
import time
import argparse
import subprocess
import shutil
import ast
import re
import logging
import sys
import asyncio
from typing import List, Dict, Any

from dotenv import load_dotenv

# Configure logging for this module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)
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
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.abspath(os.path.join(PROJECT_ROOT, "chroma_db")))

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
        logger.error(f"Error parsing functions from {file_path}: {e}")
        # Fallback to whole file
        functions.append({
            "name": os.path.basename(file_path),
            "type": "file", 
            "code": file_content,
            "start_line": 1,
            "end_line": file_content.count('\n') + 1
        })
    
    return functions

async def fetch_repo_code(repo_full_name: str):
    """
    Clones the repository and extracts code files with function-level chunking.
    Uses async processing to prevent timeouts.
    """
    logger.info("Cloning repository for code analysis...")
    
    # Use system temp directory to avoid permission issues
    import tempfile
    temp_base_dir = tempfile.mkdtemp(prefix=f"mcp_clone_{repo_full_name.replace('/', '_')}_")
    temp_dir = os.path.join(temp_base_dir, "repo")
    
    logger.info(f"Using temporary directory: {temp_base_dir}")
    
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
        logger.info("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to clone repository: {e.stderr}")
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
            logger.warning(f"Failed to clone public repository: {e2.stderr}")
            if os.path.exists(temp_base_dir):
                shutil.rmtree(temp_base_dir)
            return []

    logger.info("Extracting code files from local clone...")
    code_chunks = []
    
    # Define code file extensions
    code_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.c', '.h', '.cs', '.php', '.rb', '.go', '.rs', '.swift']
    
    # Collect all code files first
    code_files = []
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if any(file.endswith(ext) for ext in code_extensions):
                file_path = os.path.join(root, file)
                code_files.append(file_path)
    
    logger.info(f"Found {len(code_files)} code files to process...")
    
    # Process files in batches with progress reporting
    batch_size = 10  # Process 10 files at a time
    processed_count = 0
    
    try:
        for i in range(0, len(code_files), batch_size):
            batch = code_files[i:i+batch_size]
            
            for file_path in batch:
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
                    
                    processed_count += 1
                        
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {e}")
                    processed_count += 1
            
            # Log progress and yield control back to event loop
            logger.info(f"Processed {processed_count}/{len(code_files)} code files...")
            await asyncio.sleep(0)  # Yield control to prevent timeout
            
    except Exception as e:
        logger.error(f"Error during code processing: {e}")
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_base_dir):
            shutil.rmtree(temp_base_dir)
    
    logger.info(f"Found and processed {len(code_chunks)} code chunks from {processed_count} files.")
    return code_chunks

async def fetch_repo_docs(repo_full_name: str):
    """
    Clones the repository to a temporary local directory and extracts all
    Markdown and text files. Uses async processing to prevent timeouts.
    """
    logger.info("Cloning repository for faster file access...")
    
    # Use system temp directory to avoid permission issues
    import tempfile
    temp_base_dir = tempfile.mkdtemp(prefix=f"mcp_docs_{repo_full_name.replace('/', '_')}_")
    temp_dir = os.path.join(temp_base_dir, "repo")
    
    logger.info(f"Using temporary directory: {temp_base_dir}")
    
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
        logger.info("Repository cloned successfully.")
    except subprocess.CalledProcessError as e:
        logger.warning(f"Failed to clone repository: {e.stderr}")
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
            logger.warning(f"Failed to clone public repository: {e2.stderr}")
            if os.path.exists(temp_base_dir):
                shutil.rmtree(temp_base_dir)
            return []

    logger.info("Extracting documentation files (.md, .txt) from local clone...")
    docs = []
    
    # Collect all documentation files first
    doc_files = []
    for root, _, files in os.walk(temp_dir):
        for file in files:
            if file.endswith((".md", ".txt", "README")):
                file_path = os.path.join(root, file)
                doc_files.append(file_path)
    
    logger.info(f"Found {len(doc_files)} documentation files to process...")
    
    # Process files in batches with progress reporting
    batch_size = 20  # Process 20 files at a time for docs
    processed_count = 0
    
    try:
        for i in range(0, len(doc_files), batch_size):
            batch = doc_files[i:i+batch_size]
            
            for file_path in batch:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # Get the relative path to use as the source identifier
                    relative_path = os.path.relpath(file_path, temp_dir)
                    docs.append({"source": relative_path, "content": content, "type": "doc"})
                    processed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {e}")
                    processed_count += 1
            
            # Log progress and yield control back to event loop
            logger.info(f"Processed {processed_count}/{len(doc_files)} documentation files...")
            await asyncio.sleep(0)  # Yield control to prevent timeout
            
    except Exception as e:
        logger.error(f"Error during documentation processing: {e}")
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_base_dir):
            shutil.rmtree(temp_base_dir)
    
    logger.info(f"Found and processed {len(docs)} documentation files from {processed_count} files.")
    return docs

def fetch_repo_pr_history(repo, max_prs=50):
    """Fetches merged pull request history with diffs."""
    logger.info(f"Fetching pull request history (max: {max_prs})...")
    pr_data = []
    
    try:
        # Get merged PRs (limit to recent ones to avoid rate limits)
        prs = repo.get_pulls(state="closed", sort="updated", direction="desc")
        
        count = 0
        for pr in tqdm(prs, desc="Fetching PR history"):
            if count >= max_prs:  # Apply user-specified limit
                logger.info(f"Reached maximum PR limit ({max_prs}), stopping...")
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
                    logger.warning(f"Error fetching PR #{pr.number}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"Error fetching PR history: {e}")
    
    logger.info(f"Found {len(pr_data)} merged PRs.")
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
        logger.error(f"Error during client initialization: {e}")
        exit()

def create_chroma_collection(embeddings, collection_name: str, repo_name: str = None):
    """Create or get a Chroma collection with repository-specific naming."""
    if repo_name:
        # Create repository-specific collection name
        safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
        full_collection_name = f"{safe_repo_name}_{collection_name}"
    else:
        full_collection_name = collection_name
    
    logger.info(f"Creating/connecting to Chroma collection: {full_collection_name}")
    return Chroma(
        embedding_function=embeddings,
        persist_directory=CHROMA_PERSIST_DIR,
        collection_name=full_collection_name
    )

# --- DATA FETCHING ---
def fetch_repo_docs_api(repo):
    """Fetches all Markdown and text files from the repository using GitHub API."""
    logger.info("Fetching documentation files (.md, .txt) from the repository...")
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
                    logger.warning(f"Could not decode file {file_content.path}: {e}")
    logger.info(f"Found {len(docs)} documentation files.")
    return docs

def fetch_repo_issues(repo, max_issues=100):
    """Fetches open and closed issues from the repository with a limit."""
    logger.info(f"Fetching issues (max: {max_issues})...")
    issues_data = []
    issues = repo.get_issues(state="all")
    issue_count = 0
    
    # Apply limit for issues as requested
    for issue in tqdm(issues, desc="Fetching issues"):
        if issue_count >= max_issues:
            logger.info(f"Reached maximum issue limit ({max_issues}), stopping...")
            break
            
        # Combine title, body, and comments for a complete context
        try:
            comments_text = "\n".join([comment.body for comment in issue.get_comments()])
            full_issue_text = f"Title: {issue.title}\nBody: {issue.body}\nComments:\n{comments_text}"
            
            issues_data.append({
                "source": f"issue #{issue.number}",
                "content": full_issue_text,
                "type": "issue"
            })
            issue_count += 1
        except Exception as e:
            logger.warning(f"Error processing issue #{issue.number}: {e}")
            issue_count += 1  # Still count it toward the limit
            
    logger.info(f"Found {len(issues_data)} issues.")
    return issues_data

# --- PROCESSING & UPSERTING ---
async def chunk_and_embed_and_store(documents, embeddings, collection_name: str, repo_name: str = None):
    """Chunks documents, creates embeddings, and stores in Chroma collection with async processing."""
    # Different chunking strategies based on content type
    standard_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    
    # More conservative chunking for issues and PRs to prevent explosion
    issue_pr_splitter = RecursiveCharacterTextSplitter(chunk_size=3000, chunk_overlap=200)
    
    batch_size = 50  # Smaller batches for better responsiveness
    total_documents_stored = 0
    total_chunks_created = 0
    
    logger.info(f"Processing {len(documents)} documents for collection '{collection_name}' (repo: {repo_name})...")
    
    # Create/get the Chroma collection with repository-specific naming
    chroma_collection = create_chroma_collection(embeddings, collection_name, repo_name)
    
    for i in tqdm(range(0, len(documents), batch_size), desc=f"Processing {collection_name} in batches"):
        batch_docs = documents[i:i + batch_size]
        
        all_chunks = []
        all_metadatas = []
        batch_chunks_created = 0
        
        # 1. Chunking and metadata preparation
        for doc_idx, doc in enumerate(batch_docs):
            doc_type = doc.get("type", "")
            content = doc["content"]
            content_length = len(content)
            
            # Smart chunking strategy based on document type and size
            if doc_type == "code" and content_length <= 2000:
                # Don't chunk small code blocks
                chunks = [content]
            elif doc_type in ["issue", "pr"] and content_length <= 4000:
                # Don't chunk small issues/PRs - keep them as single documents
                chunks = [content]
            elif doc_type in ["issue", "pr"]:
                # Use larger chunks for issues and PRs, limit to max 3 chunks per document
                chunks = issue_pr_splitter.split_text(content)
                # Limit chunks per issue/PR to prevent explosion
                if len(chunks) > 3:
                    logger.warning(f"Large {doc_type} with {len(chunks)} chunks, truncating to 3 chunks")
                    chunks = chunks[:3]
            else:
                # Standard chunking for documentation and other content
                chunks = standard_splitter.split_text(content)
            
            batch_chunks_created += len(chunks)
            
            for j, chunk in enumerate(chunks):
                # Create enhanced metadata based on document type
                metadata = {
                    "source": doc["source"],
                    "type": doc_type,
                    "collection_name": collection_name,
                    "chunk_index": j,
                    "original_doc_length": content_length
                }
                
                # Add type-specific metadata
                if doc_type == "code":
                    metadata.update({
                        "filePath": doc.get("filePath", ""),
                        "functionName": doc.get("functionName", ""),
                        "functionType": doc.get("functionType", ""),
                        "branch": doc.get("branch", "main"),
                        "start_line": doc.get("start_line"),
                        "end_line": doc.get("end_line")
                    })
                elif doc_type == "pr":
                    metadata.update({
                        "pr_number": doc.get("pr_number"),
                        "pr_title": doc.get("pr_title", ""),
                        "pr_url": doc.get("pr_url", ""),
                        "merged_at": doc.get("merged_at")
                    })
                elif doc_type == "issue":
                    metadata.update({
                        "issue_number": doc.get("issue_number"),
                        "issue_title": doc.get("issue_title", ""),
                        "issue_url": doc.get("issue_url", ""),
                        "created_at": doc.get("created_at"),
                        "issue_state": doc.get("state", "")
                    })
                
                all_chunks.append(chunk)
                all_metadatas.append(metadata)
            
            # Yield control every 5 documents to prevent timeouts
            if doc_idx % 5 == 0:
                await asyncio.sleep(0)
        
        total_chunks_created += batch_chunks_created
        logger.info(f"Batch {i//batch_size + 1}: {len(batch_docs)} documents → {batch_chunks_created} chunks (total chunks so far: {total_chunks_created})")
        
        if not all_chunks:
            continue

        # 2. Create Document objects for Chroma
        langchain_docs = [
            Document(page_content=chunk, metadata=metadata)
            for chunk, metadata in zip(all_chunks, all_metadatas)
        ]
        
        # 3. Add to Chroma collection in smaller sub-batches with async yielding
        sub_batch_size = 25  # Even smaller batches for better responsiveness
        for start in range(0, len(langchain_docs), sub_batch_size):
            end = start + sub_batch_size
            sub_batch = langchain_docs[start:end]
            
            try:
                # Run embedding and storage in thread to avoid blocking event loop
                logger.info(f"Embedding and storing {len(sub_batch)} documents...")
                await asyncio.to_thread(chroma_collection.add_documents, sub_batch)
                total_documents_stored += len(sub_batch)
                logger.info(f"Stored {len(sub_batch)} documents. Total: {total_documents_stored}")
                
                # Yield control after each sub-batch
                await asyncio.sleep(0)
                
            except Exception as e:
                logger.error(f"Error adding batch to Chroma: {e}")
                continue
            
    # Note: Chroma automatically persists to disk when using persist_directory
    
    logger.info(f"Finished {collection_name}. Total documents processed: {len(documents)} → Total chunks created and stored: {total_documents_stored}")
    
    # Log summary for issues and PRs to show chunking results
    if collection_name in ["issues_history", "pr_history"]:
        avg_chunks_per_doc = total_documents_stored / len(documents) if len(documents) > 0 else 0
        logger.info(f"Chunking summary: {len(documents)} {collection_name.split('_')[0]}s → {total_documents_stored} chunks (avg: {avg_chunks_per_doc:.1f} chunks per {collection_name.split('_')[0]})")
    
    return total_documents_stored


# --- VALIDATION & STATS ---
def validate_repo_exists(repo_name: str) -> bool:
    """Validate that a GitHub repository exists and is accessible."""
    try:
        github_client, _ = initialize_clients()
        repo = github_client.get_repo(repo_name)
        return True
    except Exception as e:
        logger.error(f"Repository validation failed: {e}")
        return False

def get_repo_stats(repo_name: str) -> Dict[str, Any]:
    """Get statistics for an ingested repository."""
    try:
        # Initialize embeddings to access ChromaDB
        _, embeddings = initialize_clients()
        
        # Get stats for each collection
        collections_stats = {}
        collections = [COLLECTION_DOCS, COLLECTION_ISSUES, COLLECTION_REPO_CODE, COLLECTION_PR_HISTORY]
        
        for collection_name in collections:
            try:
                vectorstore = create_chroma_collection(embeddings, collection_name)
                # Try to get collection info - this might not work with all Chroma versions
                try:
                    collection = vectorstore._collection
                    count = collection.count()
                    collections_stats[collection_name] = {"count": count}
                except:
                    # Fallback if direct collection access doesn't work
                    collections_stats[collection_name] = {"count": "Unknown"}
            except Exception as e:
                collections_stats[collection_name] = {"count": 0, "error": str(e)}
        
        return {
            "collections": collections_stats,
            "total_documents": sum(stats.get("count", 0) for stats in collections_stats.values() if isinstance(stats.get("count"), int)),
            "last_updated": "Unknown",
            "status": "Available"
        }
    except Exception as e:
        return {
            "collections": {},
            "total_documents": 0,
            "last_updated": "Unknown", 
            "status": f"Error: {str(e)}"
        }

# --- MAIN EXECUTION ---
# The main execution block is removed to convert this file into a library module.
# The functionality will be invoked from the main server or a dedicated script.