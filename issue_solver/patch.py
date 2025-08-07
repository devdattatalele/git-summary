# patch_generator.py

import os
import re
import json
import tempfile
import subprocess
import logging
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

from github import Github
from langchain_chroma import Chroma
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

# --- Configuration ---
load_dotenv()

# Load API keys from .env file
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")

# Chroma configuration
# Determine project root and Chroma DB directory
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
CHROMA_PERSIST_DIR = os.path.join(PROJECT_ROOT, "chroma_db")

# Validate required environment variables
required_vars = {
    'GOOGLE_API_KEY': GOOGLE_API_KEY,
    'GITHUB_TOKEN': GITHUB_TOKEN
}

for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"Required environment variable {var_name} is not set in .env file")

# --- Helper Functions ---

def initialize_chroma_clients():
    """Initialize Chroma client and vector stores for both collections."""
    logger.info("Initializing Chroma clients for patch generation...")
    try:
        # Check if Chroma database exists
        if not os.path.exists(CHROMA_PERSIST_DIR):
            raise ValueError(
                f"Chroma database not found at '{CHROMA_PERSIST_DIR}'. "
                f"Please run the ingestion script first."
            )
        
        # Initialize embeddings
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            google_api_key=GOOGLE_API_KEY
        )
        
        # Create vector stores for both collections
        pr_history_store = Chroma(
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name="pr_history"
        )
        
        repo_code_store = Chroma(
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name="repo_code_main"
        )
        
        return pr_history_store, repo_code_store
    except Exception as e:
        raise Exception(f"Failed to initialize Chroma clients: {e}")

def query_vector_stores(issue_body: str, pr_history_store, repo_code_store, k: int = 5):
    """Query both vector stores for relevant context."""
    logger.info("Querying vector stores for relevant context...")
    
    try:
        # Query PR history
        pr_results = pr_history_store.similarity_search(issue_body, k=k)
        pr_context = []
        for doc in pr_results:
            pr_context.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })
        
        # Query repository code
        code_results = repo_code_store.similarity_search(issue_body, k=k)
        code_context = []
        for doc in code_results:
            code_context.append({
                "content": doc.page_content,
                "metadata": doc.metadata
            })
        
        return pr_context, code_context
    except Exception as e:
        raise Exception(f"Failed to query vector stores: {e}")

def format_context_for_llm(pr_context: List[Dict], code_context: List[Dict]) -> str:
    """Format the retrieved context for the LLM prompt."""
    formatted_context = ""
    
    # Format PR history context
    if pr_context:
        formatted_context += "### Relevant PR History:\n"
        for i, pr in enumerate(pr_context, 1):
            pr_number = pr["metadata"].get("pr_number", "unknown")
            formatted_context += f"**PR #{pr_number}:**\n"
            formatted_context += f"{pr['content'][:500]}...\n\n"
    
    # Format code context
    if code_context:
        formatted_context += "### Relevant Code Chunks:\n"
        for i, code in enumerate(code_context, 1):
            file_path = code["metadata"].get("filePath", "unknown")
            function_name = code["metadata"].get("functionName", "")
            func_info = f" (function: {function_name})" if function_name else ""
            formatted_context += f"**File: {file_path}{func_info}:**\n"
            formatted_context += f"```\n{code['content'][:500]}...\n```\n\n"
    
    return formatted_context

def generate_patch_for_issue(issue_body: str, repo_full_name: str = None) -> Dict[str, Any]:
    """
    Generate patch suggestions for a GitHub issue.
    
    Args:
        issue_body: The body text of the GitHub issue
        repo_full_name: Optional repository name for context
        
    Returns:
        Dictionary with filesToUpdate and summaryOfChanges
    """
    logger.info("Starting patch generation process...")
    
    try:
        # Initialize vector stores
        pr_history_store, repo_code_store = initialize_chroma_clients()
        
        # Query both collections
        pr_context, code_context = query_vector_stores(issue_body, pr_history_store, repo_code_store)
        
        # Format context for LLM
        context_text = format_context_for_llm(pr_context, code_context)
        
        # Initialize LLM with rate limit handling
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0.1, 
            google_api_key=GOOGLE_API_KEY,
            max_retries=2,  # Reduce retries
            request_timeout=30  # Shorter timeout
        )
        
        # Construct the prompt
        prompt = f"""You are a senior software engineer tasked with creating precise code patches to resolve a GitHub issue.

GitHub Issue:
{issue_body}

Relevant Context:
{context_text}

Based on the issue description and the provided context from similar PRs and relevant code, generate a JSON response with the exact changes needed.

IMPORTANT REQUIREMENTS:
1. Only suggest changes to files that are directly related to the issue
2. Generate actual unified diff patches (starting with @@) that can be applied with `git apply`
3. Be conservative - only include changes that are clearly necessary
4. If the issue is too vague or complex, suggest a minimal viable fix

Return a JSON object with this exact structure:
{{
  "filesToUpdate": [
    {{
      "filePath": "path/to/file.ext",
      "functionName": "functionName or null if whole file",
      "patch": "@@ -line,count +line,count @@\\n-removed line\\n+added line"
    }}
  ],
  "summaryOfChanges": "Brief summary of what changes were made and why"
}}

Rules for patch generation:
- Use proper unified diff format with @@ headers
- Include at least 3 lines of context before and after changes
- Make minimal, focused changes
- Test your patch format carefully
- If uncertain about the exact change, provide a reasonable approximation

Generate the patches now:"""

        # Get LLM response with error handling
        try:
            response = llm.invoke(prompt)
        except Exception as e:
            error_message = str(e)
            if "429" in error_message or "quota" in error_message.lower():
                logger.warning("⚠️ Google API rate limit exceeded for patch generation")
                return {
                    "filesToUpdate": [],
                    "summaryOfChanges": "Patch generation skipped due to API rate limits. Please try again later or resolve manually."
                }
            raise e
        
        # Parse JSON response
        try:
            # Try to extract JSON from the response
            response_text = response.content if hasattr(response, 'content') else str(response)
            
            # Look for JSON block
            json_match = re.search(r'```json\s*\n(.*?)\n\s*```', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find JSON directly
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_str = response_text
            
            patch_data = json.loads(json_str)
            
            # Validate the structure
            if "filesToUpdate" not in patch_data or "summaryOfChanges" not in patch_data:
                raise ValueError("Invalid patch data structure")
            
            logger.info(f"Generated patches for {len(patch_data['filesToUpdate'])} files")
            return patch_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            logger.error(f"Raw response: {response_text}")
            # Return a default structure
            return {
                "filesToUpdate": [],
                "summaryOfChanges": "Failed to generate patches - please review manually"
            }
    
    except Exception as e:
        logger.error(f"Error in patch generation: {e}")
        return {
            "filesToUpdate": [],
            "summaryOfChanges": f"Error during patch generation: {str(e)}"
        }

def create_pr(patch_data: Dict[str, Any], repo_full_name: str, base_branch: str = "main", 
              head_branch: str = None, issue_number: int = None) -> str:
    """
    Create a GitHub PR with the generated patches.
    
    Args:
        patch_data: The patch data from generate_patch_for_issue
        repo_full_name: Repository name in "owner/repo" format
        base_branch: Base branch for the PR (default: "main")
        head_branch: Head branch name (auto-generated if None)
        issue_number: Issue number for linking (optional)
        
    Returns:
        PR URL if successful, error message if failed
    """
    logger.info("Creating GitHub PR with generated patches...")
    
    if not patch_data.get("filesToUpdate"):
        return "No patches to apply - PR creation skipped"
    
    try:
        # Initialize GitHub client
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(repo_full_name)
        
        # Generate head branch name if not provided
        if not head_branch:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            issue_ref = f"issue-{issue_number}-" if issue_number else ""
            head_branch = f"auto-patch/{issue_ref}{timestamp}"
        
        logger.info(f"Creating branch: {head_branch}")
        
        # Get the base branch reference
        base_ref = repo.get_branch(base_branch)
        base_sha = base_ref.commit.sha
        
        # Create new branch
        repo.create_git_ref(ref=f"refs/heads/{head_branch}", sha=base_sha)
        
        # Apply patches to each file
        for file_patch in patch_data["filesToUpdate"]:
            file_path = file_patch["filePath"]
            patch_content = file_patch["patch"]
            
            try:
                # Get current file content
                file_obj = repo.get_contents(file_path, ref=head_branch)
                current_content = file_obj.decoded_content.decode('utf-8')
                
                # Apply patch using a simple approach
                # Note: This is a simplified patch application
                # For production use, consider using more robust patching
                updated_content = apply_simple_patch(current_content, patch_content)
                
                if updated_content != current_content:
                    # Update the file
                    repo.update_file(
                        path=file_path,
                        message=f"Auto-patch: Update {file_path}",
                        content=updated_content,
                        sha=file_obj.sha,
                        branch=head_branch
                    )
                    logger.info(f"Updated file: {file_path}")
                else:
                    logger.info(f"No changes needed for: {file_path}")
                    
            except Exception as e:
                logger.error(f"Failed to apply patch to {file_path}: {e}")
                continue
        
        # Create PR
        pr_title = f"Auto-generated patch"
        if issue_number:
            pr_title += f" for issue #{issue_number}"
        
        pr_body = f"""This PR was automatically generated to address the reported issue.

## Summary of Changes
{patch_data['summaryOfChanges']}

## Files Modified
"""
        for file_patch in patch_data["filesToUpdate"]:
            pr_body += f"- `{file_patch['filePath']}`"
            if file_patch.get('functionName'):
                pr_body += f" (function: {file_patch['functionName']})"
            pr_body += "\n"
        
        if issue_number:
            pr_body += f"\nCloses #{issue_number}"
        
        pr_body += "\n\n> ⚠️ **Note**: This PR was generated automatically. Please review all changes carefully before merging."
        
        # Create the PR as a draft
        pr = repo.create_pull(
            title=pr_title,
            body=pr_body,
            head=head_branch,
            base=base_branch,
            draft=True
        )
        
        logger.info(f"Successfully created PR: {pr.html_url}")
        return pr.html_url
        
    except Exception as e:
        error_msg = f"Failed to create PR: {e}"
        logger.error(error_msg)
        return error_msg

def apply_simple_patch(content: str, patch: str) -> str:
    """
    Apply a simple unified diff patch to content.
    
    Note: This is a basic implementation. For production use,
    consider using more robust patching libraries.
    """
    lines = content.split('\n')
    patch_lines = patch.split('\n')
    
    # Find the @@ header
    header_pattern = r'@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@'
    
    for i, line in enumerate(patch_lines):
        match = re.match(header_pattern, line)
        if match:
            old_start = int(match.group(1)) - 1  # Convert to 0-based indexing
            old_count = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3)) - 1
            new_count = int(match.group(4)) if match.group(4) else 1
            
            # Apply the patch
            patch_content = patch_lines[i+1:]  # Skip the header
            
            # Simple implementation: find lines to remove and add
            lines_to_remove = []
            lines_to_add = []
            
            for patch_line in patch_content:
                if patch_line.startswith('-'):
                    lines_to_remove.append(patch_line[1:])
                elif patch_line.startswith('+'):
                    lines_to_add.append(patch_line[1:])
            
            # Apply changes (simplified approach)
            # This is a basic implementation - in production, use proper diff tools
            if lines_to_remove and lines_to_add:
                # Find and replace the section
                for j, remove_line in enumerate(lines_to_remove):
                    for k in range(old_start, min(old_start + old_count, len(lines))):
                        if lines[k].strip() == remove_line.strip():
                            if j < len(lines_to_add):
                                lines[k] = lines_to_add[j]
                            break
            
            break
    
    return '\n'.join(lines)

# --- Main Functions for Integration ---

def generate_and_create_pr(issue_body: str, repo_full_name: str, issue_number: int = None, 
                          complexity: int = 5, max_complexity: int = 4) -> Dict[str, Any]:
    """
    Main function to generate patches and create PR.
    
    Args:
        issue_body: The GitHub issue body text
        repo_full_name: Repository name in "owner/repo" format  
        issue_number: Issue number for linking
        complexity: Issue complexity (1-5 scale)
        max_complexity: Maximum complexity to auto-create PR
        
    Returns:
        Dict with patch data and PR URL
    """
    logger.info(f"Processing issue for patch generation (complexity: {complexity})")
    
    # Generate patches
    patch_data = generate_patch_for_issue(issue_body, repo_full_name)
    
    # Only create PR if complexity is low enough or if explicitly requested
    pr_url = None
    if complexity <= max_complexity and patch_data.get("filesToUpdate"):
        pr_url = create_pr(patch_data, repo_full_name, issue_number=issue_number)
    else:
        if complexity > max_complexity:
            pr_url = f"PR creation skipped - complexity ({complexity}) exceeds threshold ({max_complexity})"
        else:
            pr_url = "No patches generated - PR creation skipped"
    
    return {
        "patch_data": patch_data,
        "pr_url": pr_url,
        "created_pr": pr_url.startswith("https://") if pr_url else False
    }

# The main execution block is removed to convert this file into a library module. 