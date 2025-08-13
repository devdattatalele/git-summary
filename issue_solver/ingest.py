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
    """Optimized function extraction with smarter chunking for better performance."""
    functions = []
    file_ext = os.path.splitext(file_path)[1].lower()
    file_size = len(file_content)
    
    # PERFORMANCE OPTIMIZATION: For large files, prefer file-level chunks over micro-functions
    # This reduces the total chunk count significantly while preserving code context
    
    try:
        # STRATEGY 1: Small files - keep whole for perfect context
        if file_size <= 3000:
            functions.append({
                "name": os.path.basename(file_path),
                "type": "file",
                "code": file_content,
                "start_line": 1,
                "end_line": file_content.count('\n') + 1
            })
            return functions
        
        # STRATEGY 2: Medium files - extract major functions/classes only
        if file_ext in ['.py'] and file_size <= 10000:
            tree = ast.parse(file_content)
            major_items = []
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    start_line = node.lineno
                    lines = file_content.split('\n')
                    
                    # Smart end detection with size limits
                    end_line = min(len(lines), start_line + 50)  # Limit function size
                    base_indent = len(lines[start_line - 1]) - len(lines[start_line - 1].lstrip())
                    
                    for i in range(start_line, min(len(lines), start_line + 50)):
                        line = lines[i]
                        if line.strip() and len(line) - len(line.lstrip()) <= base_indent and i > start_line:
                            end_line = i
                            break
                    
                    func_code = '\n'.join(lines[start_line-1:end_line])
                    
                    # Only include substantial functions to reduce noise
                    if len(func_code) > 100:  # Skip tiny functions
                        major_items.append({
                            "name": node.name,
                            "type": "class" if isinstance(node, ast.ClassDef) else "function",
                            "code": func_code,
                            "start_line": start_line,
                            "end_line": end_line
                        })
            
            # If we found substantial functions, use them; otherwise use whole file
            if major_items and len(major_items) <= 5:  # Don't create too many chunks
                functions.extend(major_items)
            else:
                # Too many small functions or no functions - use file-level chunk
                functions.append({
                    "name": os.path.basename(file_path),
                    "type": "file",
                    "code": file_content,
                    "start_line": 1,
                    "end_line": file_content.count('\n') + 1
                })
        
        # STRATEGY 3: Large files - create logical sections
        elif file_size > 10000:
            # For very large files, create 2-3 logical sections instead of many small functions
            lines = file_content.split('\n')
            total_lines = len(lines)
            section_size = total_lines // 3  # Create 3 sections max
            
            sections = []
            for i in range(0, total_lines, section_size):
                end_idx = min(i + section_size, total_lines)
                section_code = '\n'.join(lines[i:end_idx])
                
                sections.append({
                    "name": f"{os.path.basename(file_path)}_section_{len(sections)+1}",
                    "type": "section",
                    "code": section_code,
                    "start_line": i + 1,
                    "end_line": end_idx
                })
                
                if len(sections) >= 3:  # Max 3 sections per file
                    break
            
            functions.extend(sections)
        
        # STRATEGY 4: JavaScript/TypeScript - simplified approach
        elif file_ext in ['.js', '.jsx', '.ts', '.tsx']:
            # For JS files, use file-level or simple splitting for large files
            if file_size <= 8000:
                functions.append({
                    "name": os.path.basename(file_path),
                    "type": "file",
                    "code": file_content,
                    "start_line": 1,
                    "end_line": file_content.count('\n') + 1
                })
            else:
                # Split large JS files into logical sections
                lines = file_content.split('\n')
                section_size = len(lines) // 2  # Max 2 sections for JS
                
                for i in range(0, len(lines), section_size):
                    end_idx = min(i + section_size, len(lines))
                    section_code = '\n'.join(lines[i:end_idx])
                    
                    functions.append({
                        "name": f"{os.path.basename(file_path)}_part_{len(functions)+1}",
                        "type": "section",
                        "code": section_code,
                        "start_line": i + 1,
                        "end_line": end_idx
                    })
                    
                    if len(functions) >= 2:  # Max 2 sections
                        break
        
        # FALLBACK: Default to whole file for unknown types
        else:
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
    Optimized repository code extraction with performance improvements and chunk reduction.
    Prioritizes important files and reduces total chunk count significantly.
    """
    import time
    start_time = time.time()
    logger.info("🚀 OPTIMIZED code extraction starting...")
    
    # Use system temp directory to avoid permission issues
    import tempfile
    temp_base_dir = tempfile.mkdtemp(prefix=f"mcp_clone_{repo_full_name.replace('/', '_')}_")
    temp_dir = os.path.join(temp_base_dir, "repo")
    
    logger.info(f"📁 Using temporary directory: {temp_base_dir}")
    
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
        logger.info("✅ Repository cloned successfully.")
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

    logger.info("🔍 Analyzing code files with smart prioritization...")
    code_chunks = []
    
    # OPTIMIZED: Priority-based file selection to reduce noise
    priority_extensions = ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.go', '.rs']
    secondary_extensions = ['.cpp', '.c', '.h', '.cs', '.php', '.rb', '.swift']
    
    # Collect files with priority system
    priority_files = []
    secondary_files = []
    
    for root, _, files in os.walk(temp_dir):
        # Skip common non-essential directories to reduce processing
        if any(skip_dir in root for skip_dir in [
            'node_modules', '.git', 'dist', 'build', 'coverage', 
            '__pycache__', '.pytest_cache', 'venv', 'env'
        ]):
            continue
            
        for file in files:
            file_path = os.path.join(root, file)
            file_size = os.path.getsize(file_path)
            
            # Skip very large files to prevent memory issues
            if file_size > 500000:  # 500KB limit
                logger.warning(f"Skipping large file: {file} ({file_size} bytes)")
                continue
                
            if any(file.endswith(ext) for ext in priority_extensions):
                priority_files.append(file_path)
            elif any(file.endswith(ext) for ext in secondary_extensions):
                secondary_files.append(file_path)
    
    # Limit total files to process (prevent excessive processing)
    max_priority_files = 250  # Process up to 150 priority files
    max_secondary_files = 150   # Process up to 50 secondary files
    
    files_to_process = priority_files[:max_priority_files] + secondary_files[:max_secondary_files]
    
    logger.info(f"📊 File analysis: {len(priority_files)} priority, {len(secondary_files)} secondary")
    logger.info(f"🎯 Processing {len(files_to_process)} files (limited for performance)")
    
    # Process files efficiently with larger batches
    batch_size = 25  # Larger batches for efficiency
    processed_count = 0
    
    try:
        for i in range(0, len(files_to_process), batch_size):
            batch_start = time.time()
            batch = files_to_process[i:i+batch_size]
            
            for file_path in batch:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    # Skip empty or very small files
                    if len(content.strip()) < 50:
                        processed_count += 1
                        continue
                    
                    # Get the relative path to use as the source identifier
                    relative_path = os.path.relpath(file_path, temp_dir)
                    
                    # Extract functions/sections with optimized logic
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
            
            # Enhanced progress logging
            batch_time = time.time() - batch_start
            logger.info(f"📦 Processed batch {i//batch_size + 1}: {len(batch)} files → {processed_count} total (⏱️ {batch_time:.1f}s)")
            
            # Smart yielding based on time
            if batch_time > 2.0:
                await asyncio.sleep(0.02)  # Longer yield for slow batches
            else:
                await asyncio.sleep(0.01)  # Quick yield for fast batches
            
    except Exception as e:
        logger.error(f"Error during code processing: {e}")
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_base_dir):
            shutil.rmtree(temp_base_dir)
    
    total_time = time.time() - start_time
    efficiency_ratio = processed_count / len(code_chunks) if code_chunks else 0
    
    logger.info(f"🎉 CODE EXTRACTION COMPLETE:")
    logger.info(f"  📁 {processed_count} files processed → 📦 {len(code_chunks)} code chunks")
    logger.info(f"  📊 Efficiency: {efficiency_ratio:.2f} files/chunk (higher = better)")
    logger.info(f"  ⏱️  Total time: {total_time:.1f} seconds")
    
    return code_chunks

async def fetch_repo_docs(repo_full_name: str):
    """
    Optimized documentation extraction with intelligent prioritization and chunk reduction.
    Focuses on the most important documentation while maintaining quality.
    """
    import time
    start_time = time.time()
    logger.info("🚀 OPTIMIZED documentation extraction starting...")
    
    # Use system temp directory to avoid permission issues
    import tempfile
    temp_base_dir = tempfile.mkdtemp(prefix=f"mcp_docs_{repo_full_name.replace('/', '_')}_")
    temp_dir = os.path.join(temp_base_dir, "repo")
    
    logger.info(f"📁 Using temporary directory: {temp_base_dir}")
    
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
        logger.info("✅ Repository cloned successfully.")
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

    logger.info("📝 Analyzing documentation with smart prioritization...")
    docs = []
    
    # PRIORITY SYSTEM: Focus on most important documentation first
    priority_docs = []    # README, main docs
    important_docs = []   # API docs, guides, tutorials
    regular_docs = []     # Other markdown files
    
    # Collect documentation files with intelligent prioritization
    for root, _, files in os.walk(temp_dir):
        # Skip generated/build directories for docs
        if any(skip_dir in root.lower() for skip_dir in [
            'node_modules', '.git', 'dist', 'build', '_build', 
            '.next', '.nuxt', 'coverage', '__pycache__'
        ]):
            continue
            
        for file in files:
            if file.endswith((".md", ".txt", "README")):
                file_path = os.path.join(root, file)
                file_size = os.path.getsize(file_path)
                file_lower = file.lower()
                
                # Skip extremely large documentation files
                if file_size > 1000000:  # 1MB limit for docs
                    logger.warning(f"Skipping large doc file: {file} ({file_size} bytes)")
                    continue
                
                # PRIORITY CLASSIFICATION
                if any(priority_name in file_lower for priority_name in [
                    'readme', 'index', 'introduction', 'getting-started', 'quickstart'
                ]):
                    priority_docs.append(file_path)
                elif any(important_name in file_lower for important_name in [
                    'api', 'guide', 'tutorial', 'doc', 'manual', 'reference',
                    'install', 'setup', 'config', 'usage'
                ]):
                    important_docs.append(file_path)
                else:
                    regular_docs.append(file_path)
    
    # Smart limits to prevent doc explosion while preserving quality
    max_priority_docs = 40   # Process all important docs (READMEs, etc.)
    max_important_docs = 100  # Process many important docs  
    max_regular_docs = 200   # Limit regular docs to prevent overload
    
    # Build final processing list with priorities
    docs_to_process = (
        priority_docs[:max_priority_docs] + 
        important_docs[:max_important_docs] + 
        regular_docs[:max_regular_docs]
    )
    
    logger.info(f"📊 Documentation analysis:")
    logger.info(f"  🎯 Priority docs: {len(priority_docs)} (processing {min(len(priority_docs), max_priority_docs)})")
    logger.info(f"  📖 Important docs: {len(important_docs)} (processing {min(len(important_docs), max_important_docs)})")  
    logger.info(f"  📄 Regular docs: {len(regular_docs)} (processing {min(len(regular_docs), max_regular_docs)})")
    logger.info(f"  🎯 Total processing: {len(docs_to_process)} files")
    
    # Process files efficiently with larger batches
    batch_size = 30  # Larger batches for docs
    processed_count = 0
    
    try:
        for i in range(0, len(docs_to_process), batch_size):
            batch_start = time.time()
            batch = docs_to_process[i:i+batch_size]
            
            for file_path in batch:
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    
                    # Skip empty or very small files
                    if len(content.strip()) < 30:
                        processed_count += 1
                        continue
                    
                    # Get the relative path to use as the source identifier
                    relative_path = os.path.relpath(file_path, temp_dir)
                    
                    # Determine doc priority for metadata
                    doc_priority = "priority" if file_path in priority_docs else ("important" if file_path in important_docs else "regular")
                    
                    docs.append({
                        "source": relative_path, 
                        "content": content, 
                        "type": "doc",
                        "doc_priority": doc_priority,
                        "doc_size": len(content)
                    })
                    processed_count += 1
                    
                except Exception as e:
                    logger.warning(f"Could not read file {file_path}: {e}")
                    processed_count += 1
            
            # Enhanced progress logging
            batch_time = time.time() - batch_start
            logger.info(f"📦 Processed batch {i//batch_size + 1}: {len(batch)} docs → {processed_count} total (⏱️ {batch_time:.1f}s)")
            
            # Smart yielding based on time
            if batch_time > 2.0:
                await asyncio.sleep(0.02)  # Longer yield for slow batches
            else:
                await asyncio.sleep(0.01)  # Quick yield for fast batches
            
    except Exception as e:
        logger.error(f"Error during documentation processing: {e}")
    finally:
        # Clean up the temporary directory
        if os.path.exists(temp_base_dir):
            shutil.rmtree(temp_base_dir)
    
    total_time = time.time() - start_time
    
    logger.info(f"🎉 DOCUMENTATION EXTRACTION COMPLETE:")
    logger.info(f"  📄 {processed_count} files processed → 📦 {len(docs)} documentation chunks")
    logger.info(f"  📊 Quality preserved with intelligent prioritization")
    logger.info(f"  ⏱️  Total time: {total_time:.1f} seconds")
    
    return docs

def fetch_repo_pr_history(repo, max_prs=50):
    """Optimized PR history fetching with smart content filtering and diff size limits."""
    logger.info(f"🚀 OPTIMIZED PR history fetching (max: {max_prs})...")
    pr_data = []
    count = 0
    
    try:
        # Get merged PRs (limit to recent ones to avoid rate limits)
        prs = repo.get_pulls(state="closed", sort="updated", direction="desc")
        
        for pr in tqdm(prs, desc="Fetching PR history efficiently", total=max_prs):
            if count >= max_prs:  # Apply user-specified limit
                logger.info(f"✅ Reached maximum PR limit ({max_prs}), stopping...")
                break
                
            if pr.merged:
                try:
                    # OPTIMIZATION: Limit file processing to avoid huge PRs
                    files = list(pr.get_files())
                    max_files_to_process = 10  # Only process first 10 files for efficiency
                    files_to_process = files[:max_files_to_process]
                    
                    # Start with PR metadata
                    pr_description = pr.body or "No description"
                    if len(pr_description) > 1500:
                        pr_description = pr_description[:1500] + "...[truncated]"
                    
                    pr_content = f"Title: {pr.title}\nDescription: {pr_description}\n"
                    
                    # Add file changes with size limits
                    diff_content = ""
                    total_diff_size = 0
                    max_total_diff_size = 8000  # Limit total diff content
                    
                    for file in files_to_process:
                        if file.patch and total_diff_size < max_total_diff_size:
                            # Limit individual file patch size
                            file_patch = file.patch
                            if len(file_patch) > 2000:
                                file_patch = file_patch[:2000] + "\n...[diff truncated]"
                            
                            file_diff = f"\nFile: {file.filename}\nStatus: {file.status}\nDiff:\n{file_patch}\n"
                            
                            # Check if adding this diff would exceed our limit
                            if total_diff_size + len(file_diff) > max_total_diff_size:
                                diff_content += f"\n[Additional files truncated for size...]"
                                break
                                
                            diff_content += file_diff
                            total_diff_size += len(file_diff)
                    
                    pr_content += diff_content
                    
                    # Add summary if we truncated files
                    if len(files) > max_files_to_process:
                        pr_content += f"\n[Note: Processed {max_files_to_process} of {len(files)} files]"
                    
                    pr_data.append({
                        "source": f"PR #{pr.number}",
                        "content": pr_content,
                        "type": "pr",
                        "pr_number": pr.number,
                        "pr_title": pr.title,
                        "pr_url": pr.html_url,
                        "merged_at": pr.merged_at.isoformat() if pr.merged_at else None,
                        "files_count": len(files),
                        "files_processed": len(files_to_process)
                    })
                    count += 1
                    
                    # Progress feedback every 10 PRs
                    if count % 10 == 0:
                        logger.info(f"📊 Processed {count}/{max_prs} PRs...")
                    
                except Exception as e:
                    logger.warning(f"⚠️ Error fetching PR #{pr.number}: {e}")
                    continue
                    
    except Exception as e:
        logger.error(f"❌ Error fetching PR history: {e}")
    
    efficiency_msg = f"merged PRs with optimized diff processing"
    logger.info(f"✅ PR fetching complete: {len(pr_data)} {efficiency_msg}")
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
    """Optimized issue fetching with smart content filtering and reduced processing time."""
    logger.info(f"🚀 OPTIMIZED issue fetching (max: {max_issues})...")
    issues_data = []
    issue_count = 0
    
    try:
        # Get issues with optimized ordering (recent first)
        issues = repo.get_issues(state="all", sort="updated", direction="desc")
        
        # Apply limit for issues as requested with progress tracking
        for issue in tqdm(issues, desc="Fetching issues efficiently", total=max_issues):
            if issue_count >= max_issues:
                logger.info(f"✅ Reached maximum issue limit ({max_issues}), stopping...")
                break
                
            try:
                # OPTIMIZATION: Limit comment fetching to reduce API calls and processing time
                max_comments = 5  # Only get first 5 comments for context
                comments = list(issue.get_comments())[:max_comments]
                
                # Build issue content with size limits
                comments_text = ""
                if comments:
                    comment_parts = []
                    for comment in comments:
                        if comment.body and len(comment.body.strip()) > 10:
                            # Limit comment length to prevent huge issues
                            comment_text = comment.body[:1000] + "..." if len(comment.body) > 1000 else comment.body
                            comment_parts.append(comment_text)
                        
                        # Stop if we have enough comment content
                        if len("\n".join(comment_parts)) > 2000:
                            break
                    
                    comments_text = "\n---\n".join(comment_parts)
                
                # Limit issue body size
                issue_body = issue.body or ""
                if len(issue_body) > 3000:
                    issue_body = issue_body[:3000] + "...[truncated]"
                
                # Create concise but informative issue content
                full_issue_text = f"Title: {issue.title}\nState: {issue.state}\nBody: {issue_body}"
                if comments_text:
                    full_issue_text += f"\nComments:\n{comments_text}"
                
                issues_data.append({
                    "source": f"issue #{issue.number}",
                    "content": full_issue_text,
                    "type": "issue",
                    "issue_number": issue.number,
                    "issue_title": issue.title,
                    "issue_url": issue.html_url,
                    "created_at": issue.created_at.isoformat() if issue.created_at else None,
                    "state": issue.state
                })
                issue_count += 1
                
                # Progress feedback every 25 issues
                if issue_count % 25 == 0:
                    logger.info(f"📊 Processed {issue_count}/{max_issues} issues...")
                
            except Exception as e:
                logger.warning(f"⚠️ Error processing issue #{issue.number}: {e}")
                issue_count += 1  # Still count it toward the limit
                continue
                
    except Exception as e:
        logger.error(f"❌ Error fetching issues: {e}")
    
    efficiency_msg = f"issues with optimized content filtering"
    logger.info(f"✅ Issue fetching complete: {len(issues_data)} {efficiency_msg}")
    return issues_data

# --- PROCESSING & UPSERTING ---
async def chunk_and_embed_and_store(documents, embeddings, collection_name: str, repo_name: str = None):
    """Optimized chunking and embedding with performance improvements and timeout prevention."""
    import time
    
    # OPTIMIZED CHUNKING STRATEGIES - Much larger chunks to reduce total count
    # Documentation: Large chunks for better context, minimal splitting
    doc_splitter = RecursiveCharacterTextSplitter(chunk_size=4000, chunk_overlap=200)
    
    # Code: Even larger chunks to preserve function/class integrity
    code_splitter = RecursiveCharacterTextSplitter(chunk_size=6000, chunk_overlap=300)
    
    # Issues/PRs: Moderate chunks but aggressive limits
    issue_pr_splitter = RecursiveCharacterTextSplitter(chunk_size=5000, chunk_overlap=250)
    
    # PERFORMANCE OPTIMIZATIONS
    batch_size = 100  # Larger batches for efficiency
    embedding_batch_size = 100  # Much larger embedding batches
    total_documents_stored = 0
    total_chunks_created = 0
    start_time = time.time()
    
    logger.info(f"🚀 OPTIMIZED Processing {len(documents)} documents for collection '{collection_name}' (repo: {repo_name})...")
    logger.info(f"📊 Target: Minimize chunks while preserving quality for {collection_name}")
    
    # Create/get the Chroma collection with repository-specific naming
    chroma_collection = create_chroma_collection(embeddings, collection_name, repo_name)
    
    # Process in larger batches for efficiency
    for i in tqdm(range(0, len(documents), batch_size), desc=f"Processing {collection_name} efficiently"):
        batch_start_time = time.time()
        batch_docs = documents[i:i + batch_size]
        
        all_chunks = []
        all_metadatas = []
        batch_chunks_created = 0
        
        # 1. INTELLIGENT CHUNKING based on content importance
        for doc_idx, doc in enumerate(batch_docs):
            doc_type = doc.get("type", "")
            content = doc["content"]
            content_length = len(content)
            
            # CONTENT-AWARE CHUNKING STRATEGY
            if doc_type == "doc":
                # DOCUMENTATION - Highest priority, preserve context
                if content_length <= 3000:
                    # Small docs: keep whole for perfect context
                    chunks = [content]
                elif content_length <= 8000:
                    # Medium docs: minimal chunking
                    chunks = doc_splitter.split_text(content)
                    if len(chunks) > 3:
                        # Merge small chunks to reduce total count
                        merged_chunks = []
                        current_chunk = ""
                        for chunk in chunks:
                            if len(current_chunk + chunk) <= 5000:
                                current_chunk += "\n\n" + chunk if current_chunk else chunk
                            else:
                                if current_chunk:
                                    merged_chunks.append(current_chunk)
                                current_chunk = chunk
                        if current_chunk:
                            merged_chunks.append(current_chunk)
                        chunks = merged_chunks[:3]  # Max 3 chunks for docs
                else:
                    # Large docs: controlled chunking
                    chunks = doc_splitter.split_text(content)[:4]  # Max 4 chunks for large docs
                    
            elif doc_type == "code":
                # CODE - Second highest priority, preserve function boundaries
                if content_length <= 4000:
                    # Small code: keep whole to preserve structure
                    chunks = [content]
                elif content_length <= 10000:
                    # Medium code: careful chunking
                    chunks = code_splitter.split_text(content)
                    if len(chunks) > 2:
                        chunks = chunks[:2]  # Max 2 chunks for code files
                else:
                    # Large code: strategic chunking
                    chunks = code_splitter.split_text(content)[:3]  # Max 3 chunks for large code
                    
            elif doc_type in ["issue", "pr"]:
                # ISSUES/PRs - Can be more aggressive to save processing time
                if content_length <= 6000:
                    # Small/medium: keep whole
                    chunks = [content]
                else:
                    # Large: aggressive chunking with strict limits
                    chunks = issue_pr_splitter.split_text(content)
                    chunks = chunks[:2]  # Max 2 chunks for issues/PRs
            else:
                # Fallback: Conservative chunking
                if content_length <= 4000:
                    chunks = [content]
                else:
                    chunks = doc_splitter.split_text(content)[:3]
            
            batch_chunks_created += len(chunks)
            
            # Create metadata efficiently
            for j, chunk in enumerate(chunks):
                metadata = {
                    "source": doc["source"],
                    "type": doc_type,
                    "collection_name": collection_name,
                    "chunk_index": j,
                    "original_doc_length": content_length,
                    "total_chunks": len(chunks)
                }
                
                # Add type-specific metadata only when needed
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
            
            # Smart yielding based on time and count
            if doc_idx % 10 == 0 or time.time() - batch_start_time > 2.0:
                await asyncio.sleep(0.01)  # Micro-yield to prevent timeout
        
        total_chunks_created += batch_chunks_created
        batch_time = time.time() - batch_start_time
        
        # Enhanced progress logging
        logger.info(f"📦 Batch {i//batch_size + 1}: {len(batch_docs)} docs → {batch_chunks_created} chunks (⏱️ {batch_time:.1f}s)")
        logger.info(f"📊 Total progress: {total_chunks_created} chunks from {i + len(batch_docs)} docs")
        
        if not all_chunks:
            continue

        # 2. EFFICIENT DOCUMENT CREATION
        langchain_docs = [
            Document(page_content=chunk, metadata=metadata)
            for chunk, metadata in zip(all_chunks, all_metadatas)
        ]
        
        # 3. OPTIMIZED EMBEDDING AND STORAGE
        # Use much larger batches for embedding efficiency
        for start in range(0, len(langchain_docs), embedding_batch_size):
            end = start + embedding_batch_size
            sub_batch = langchain_docs[start:end]
            embed_start_time = time.time()
            
            try:
                # Single large embedding call for efficiency
                await asyncio.to_thread(chroma_collection.add_documents, sub_batch)
                total_documents_stored += len(sub_batch)
                embed_time = time.time() - embed_start_time
                
                # Concise progress logging
                logger.info(f"✅ Embedded {len(sub_batch)} chunks (⏱️ {embed_time:.1f}s) | Total: {total_documents_stored}")
                
                # Intelligent yielding based on time
                if embed_time > 1.0:
                    await asyncio.sleep(0.05)  # Longer yield for slow operations
                else:
                    await asyncio.sleep(0.01)  # Quick yield for fast operations
                
            except Exception as e:
                logger.error(f"❌ Embedding error: {e}")
                continue
        
        # Progress checkpoint every batch
        total_time = time.time() - start_time
        if total_time > 10:  # Every 10 seconds, give progress update
            remaining_docs = len(documents) - (i + len(batch_docs))
            logger.info(f"🔄 PROGRESS: {total_documents_stored} chunks stored | {remaining_docs} docs remaining")
            start_time = time.time()  # Reset timer
    
    # Final summary with efficiency metrics
    total_time = time.time() - start_time
    efficiency_ratio = len(documents) / total_documents_stored if total_documents_stored > 0 else 0
    
    logger.info(f"🎉 COMPLETED {collection_name}:")
    logger.info(f"  📄 {len(documents)} documents → 📦 {total_documents_stored} chunks")
    logger.info(f"  📊 Efficiency ratio: {efficiency_ratio:.2f} docs/chunk (higher = better)")
    logger.info(f"  ⏱️  Total time: {total_time:.1f} seconds")
    
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