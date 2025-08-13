# analyze_issue.py
import os
import re
import json
import argparse
import logging
from datetime import datetime
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

from github import Github
# --- LangChain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools.retriever import create_retriever_tool
from langchain_core.prompts import ChatPromptTemplate

# --- Google Docs API Imports ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Patch Generator Import ---
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# --- Configuration ---
load_dotenv()

# Load API keys from .env file
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GOOGLE_DOCS_ID = os.getenv("GOOGLE_DOCS_ID")

# Chroma configuration
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", os.path.abspath(os.path.join(PROJECT_ROOT, "chroma_db")))
COLLECTION_ISSUES = "issues_history"

# Patch generator configuration
ENABLE_PATCH_GENERATION = os.getenv("ENABLE_PATCH_GENERATION", "true").lower() == "true"
MAX_COMPLEXITY_FOR_AUTO_PR = int(os.getenv("MAX_COMPLEXITY_FOR_AUTO_PR", "4"))

# Validate required environment variables (only check truly required ones)
required_vars = {
    'GOOGLE_API_KEY': GOOGLE_API_KEY,
    'GITHUB_TOKEN': GITHUB_TOKEN
}

for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"Required environment variable {var_name} is not set in .env file")

# GOOGLE_DOCS_ID is optional - log warning if not present
if not GOOGLE_DOCS_ID:
    logger.warning("GOOGLE_DOCS_ID not set - analysis results will not be saved to Google Docs")

# Google Docs API scopes
SCOPES = ["https://www.googleapis.com/auth/documents"]

# --- Helper Functions ---

def parse_github_url(url: str):
    """Parses a GitHub issue URL to get owner, repo, and issue number."""
    match = re.search(r"github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        raise ValueError("Invalid GitHub issue URL format. Expected: https://github.com/owner/repo/issues/number")
    return match.group(1), match.group(2), int(match.group(3))

def get_github_issue(owner: str, repo_name: str, issue_number: int):
    """Fetches issue data from GitHub."""
    logger.info(f"Fetching issue '{owner}/{repo_name}#{issue_number}' from GitHub...")
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(number=issue_number)
        return issue
    except Exception as e:
        raise Exception(f"Failed to fetch GitHub issue: {e}")

def initialize_chroma_retriever(repo_name: str = None):
    """Initializes the Chroma vector store and retriever tool with repository-specific collection."""
    logger.info("Initializing Chroma vector store and retriever...")
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
        
        # Create repository-specific collection name for issues
        if repo_name:
            safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
            collection_name = f"{safe_repo_name}_{COLLECTION_ISSUES}"
        else:
            collection_name = COLLECTION_ISSUES
            
        logger.info(f"Loading Chroma collection: {collection_name}")
        chroma_store = Chroma(
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name=collection_name
        )
        
        # Create retriever
        retriever = chroma_store.as_retriever(
            search_kwargs={"k": 5}
        )
        
        # This creates the tool the agent can use
        tool = create_retriever_tool(
            retriever,
            "github_knowledge_base_search",
            "Search the knowledge base for relevant past issues and documentation. Use this to find context for a new GitHub issue.",
        )
        return tool
    except Exception as e:
        raise Exception(f"Failed to initialize Chroma retriever: {e}")

def create_langchain_agent(issue):
    """
    Analyzes a GitHub issue using a direct RAG chain, which is more reliable than a ReAct agent.
    """
    logger.info("Initializing LangChain RAG Chain...")
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-flash", 
            temperature=0.2, 
            google_api_key=GOOGLE_API_KEY,
            max_retries=2,
            request_timeout=45
        )
        
        repo_name = issue.repository.full_name
        # Build a retriever directly for this repository's issues collection
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001",
            google_api_key=GOOGLE_API_KEY,
        )
        safe_repo_name = repo_name.replace('/', '_').replace('-', '_').lower()
        collection_name = f"{safe_repo_name}_{COLLECTION_ISSUES}"
        chroma_store = Chroma(
            embedding_function=embeddings,
            persist_directory=CHROMA_PERSIST_DIR,
            collection_name=collection_name,
        )
        retriever = chroma_store.as_retriever(search_kwargs={"k": 5})
        
        # Retrieve context up-front to keep the chain deterministic and quiet
        query = f"Title: {issue.title}\nBody: {issue.body or 'No body.'}"
        docs = retriever.get_relevant_documents(query)
        context_text = "\n\n".join(doc.page_content for doc in docs)
        
        # Prompt instructs the model to return a strict JSON object
        template = """
        You are an expert AI software engineer analyzing a GitHub issue for the '{repo_full_name}' repository.
        Use the following retrieved context from past issues and documentation to provide a detailed analysis.

        **Retrieved Context:**
        {context}

        **Current Issue Details:**
        - Title: {issue_title}
        - Body: {issue_body}
        - URL: {issue_url}

        **Your Task:**
        Based on the context and the current issue, provide a final answer as a valid JSON object with exactly these keys:
        1. "summary": A concise, one-sentence summary of the user's problem.
        2. "proposed_solution": A detailed, step-by-step technical plan to solve the issue. Be specific about files to modify. If the context provides a clear solution, adapt it. If not, propose a logical first step.
        3. "complexity": An integer from 1 to 5 (1=Trivial, 5=Very Complex).
        4. "similar_issues": An array of strings containing the source of any relevant past issues from the context (e.g., ["issue #123", "PR #456"]). If no relevant issues are found, return an empty array [].

        **Final Answer (JSON object):**
        """
        prompt = ChatPromptTemplate.from_template(template)

        # Create a more reliable RAG chain using LCEL
        from langchain_core.output_parsers import StrOutputParser

        rag_chain = prompt | llm | StrOutputParser()

        logger.info("Running RAG chain to analyze issue...")
        
        # Prepare the input for the chain
        inputs = {
            "context": context_text,
            "issue_title": issue.title,
            "issue_body": issue.body or "No body provided.",
            "issue_url": issue.html_url,
            "repo_full_name": repo_name
        }
        
        response = rag_chain.invoke(inputs)
        return response

    except Exception as e:
        error_message = str(e)
        
        # Handle rate limit specifically
        if "429" in error_message or "quota" in error_message.lower():
            logger.warning("⚠️ Google API rate limit exceeded. Using fallback analysis...")
            return create_fallback_analysis(issue)
        
        # Handle other errors
        logger.error(f"RAG chain error: {error_message}")
        raise Exception(f"Failed to run LangChain RAG chain: {e}")

def create_fallback_analysis(issue):
    """Create a basic analysis without LLM when rate limits are hit."""
    logger.info("Creating fallback analysis based on issue content...")
    
    title = issue.title.lower()
    body = (issue.body or "").lower()
    combined_text = f"{title} {body}"
    
    # Basic keyword analysis
    complexity = 3  # Default
    if any(word in combined_text for word in ["streaming", "tool", "agent", "callback"]):
        complexity = 4
    if any(word in combined_text for word in ["bug", "error", "crash", "fail"]):
        complexity += 1
    if any(word in combined_text for word in ["simple", "easy", "typo", "documentation"]):
        complexity = max(1, complexity - 1)
    
    complexity = min(5, max(1, complexity))
    
    # Extract key information from issue
    summary = f"Issue in {issue.repository.full_name}: {issue.title}"
    
    # Basic solution template based on common patterns
    if "streaming" in combined_text and "tool" in combined_text:
        proposed_solution = """Based on the issue description, this appears to be a streaming compatibility problem with agent tools. Common solutions include:

1. **Check Agent Configuration:**
   - File: `swarms/structs/agent.py` (or similar agent implementation file)
   - Look for streaming_on parameter and tool execution methods
   - Ensure tools are compatible with streaming mode

2. **Review Tool Execution Logic:**
   - File: Agent's tool execution methods (typically `_execute_tool` or `execute_tools`)
   - Add proper error handling for streaming scenarios
   - Implement tool logging as requested

3. **Add Logging Implementation:**
   - Import logging module
   - Add log statements for tool execution start, success, and errors
   - Example: `logger.info(f"Executing tool: {tool_name}, Input: {input_data}")`

4. **Test Streaming Compatibility:**
   - Create test cases with streaming_on=True
   - Verify tool calls work properly
   - Check tool execution logs are generated"""
    else:
        proposed_solution = f"""This issue requires investigation of the codebase. Recommended approach:

1. **Identify Related Files:**
   - Search for files containing keywords from the issue: {', '.join(set(combined_text.split()[:10]))}
   - Focus on main implementation files and configuration

2. **Debug the Problem:**
   - Add logging/print statements to trace execution
   - Identify the exact failure point
   - Check error logs and stack traces

3. **Implement Fix:**
   - Based on root cause analysis
   - Add proper error handling
   - Include unit tests for the fix

4. **Verify Solution:**
   - Test the fix thoroughly
   - Ensure no regressions
   - Update documentation if needed"""
    
    # Try to get some context from the knowledge base without LLM
    try:
        repo_name = issue.repository.full_name
        retriever_tool = initialize_chroma_retriever(repo_name)
        search_results = retriever_tool.invoke({"query": f"{title} {body[:100]}"})
        if search_results and len(search_results) > 50:
            similar_issues = ["Context found in knowledge base - similar issues may exist"]
        else:
            similar_issues = []
    except:
        similar_issues = []
    
    fallback_json = {
        "summary": summary,
        "proposed_solution": proposed_solution,
        "complexity": complexity,
        "similar_issues": similar_issues
    }
    
    # Return as dictionary object, not JSON string
    return fallback_json

def parse_agent_output(raw_output: str):
    """Extracts and parses the JSON from the agent's raw output string."""
    logger.info("Parsing agent's JSON output...")
    logger.info(f"Raw output length: {len(raw_output)}")
    logger.info(f"Raw output preview: {raw_output[:200]}...")
    
    try:
        # Handle empty or invalid output
        if not raw_output or raw_output.strip() == "":
            logger.warning("Empty output received from agent")
            return {
                "summary": "Agent returned empty response",
                "proposed_solution": "Please re-run the analysis or check the issue details",
                "complexity": 3,
                "similar_issues": []
            }
        
        # Handle agent timeout message
        if "Agent stopped due to iteration limit or time limit" in raw_output:
            logger.warning("Agent hit iteration limit")
            return {
                "summary": "Analysis timed out due to complexity",
                "proposed_solution": "The issue requires manual analysis as the automated agent exceeded time limits",
                "complexity": 5,
                "similar_issues": []
            }
        
        # Try to find JSON block within ```json ... ```
        json_match = re.search(r"```json\s*\n([\s\S]*?)\n\s*```", raw_output)
        if json_match:
            json_str = json_match.group(1).strip()
            logger.info(f"Found JSON block: {json_str[:100]}...")
            return json.loads(json_str)
        
        # Try to find JSON block within ``` ... ```
        json_match = re.search(r"```\s*\n([\s\S]*?)\n\s*```", raw_output)
        if json_match:
            json_str = json_match.group(1).strip()
            logger.info(f"Found code block: {json_str[:100]}...")
            return json.loads(json_str)
        
        # Try to find JSON object directly (look for { ... })
        json_match = re.search(r"(\{[\s\S]*\})", raw_output)
        if json_match:
            json_str = json_match.group(1)
            logger.info(f"Found JSON object: {json_str[:100]}...")
            return json.loads(json_str)
        
        # Extract from "Final Answer:" section
        final_answer_match = re.search(r"Final Answer:\s*([\s\S]*?)(?:\n\n|$)", raw_output)
        if final_answer_match:
            answer_text = final_answer_match.group(1).strip()
            logger.info(f"Found Final Answer: {answer_text[:100]}...")
            # Try to parse as JSON
            return json.loads(answer_text)
        
        # If no JSON found, create a summary from the text
        logger.info("No JSON found, creating summary from text")
        return {
            "summary": "Could not parse structured response from agent",
            "proposed_solution": f"Raw agent output: {raw_output[:500]}...",
            "complexity": 3,
            "similar_issues": []
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {e}")
        logger.error(f"Attempted to parse: {json_str[:200] if 'json_str' in locals() else 'No JSON string found'}...")
        
        # Return a default structure with some extracted info
        return {
            "summary": "Could not parse agent response as JSON",
            "proposed_solution": f"Agent provided response but JSON parsing failed. Raw output: {raw_output[:300]}...",
            "complexity": 3,
            "similar_issues": []
        }


def generate_patches_for_issue(issue, analysis):
    """Generate patches for the issue if conditions are met."""
    logger.info("Evaluating issue for patch generation...")
    
    if not ENABLE_PATCH_GENERATION:
        logger.info("Patch generation is disabled (ENABLE_PATCH_GENERATION=false)")
        return None
    
    try:
        complexity = analysis.get('complexity', 5)
        issue_body = f"Title: {issue.title}\n\nBody: {issue.body or 'No description provided.'}"
        
        # Import patch generation function
        from .patch import generate_patch_for_issue
        
        # Generate patches only (PR creation is now handled by the official GitHub server)
        result = generate_patch_for_issue(
            issue_body=issue_body,
            repo_full_name=issue.repository.full_name
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error in patch generation: {e}")
        return {
            "patch_data": {"filesToUpdate": [], "summaryOfChanges": f"Error: {str(e)}"},
            "pr_url": f"Patch generation failed: {str(e)}",
            "created_pr": False
        }

def append_to_google_doc(text_to_append: str):
    """Handles authentication and appends text to the specified Google Doc."""
    try:
        creds = None
        if os.path.exists("token.json"):
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        
        # If there are no (valid) credentials, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists("credentials.json"):
                    raise FileNotFoundError("credentials.json file not found. Please download it from Google Cloud Console.")
                flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open("token.json", "w") as token:
                token.write(creds.to_json())
        
        logger.info("Appending analysis to Google Doc...")
        service = build("docs", "v1", credentials=creds)
        requests = [
            {
                "insertText": {
                    "location": {"index": 1}, # Insert at the beginning of the document
                    "text": text_to_append,
                }
            }
        ]
        service.documents().batchUpdate(documentId=GOOGLE_DOCS_ID, body={"requests": requests}).execute()
        logger.info("Successfully updated Google Doc.")
    except Exception as e:
        logger.error(f"An error occurred while updating Google Docs: {e}")
        logger.info("The analysis will be printed to console instead:")
        logger.info(text_to_append)

# --- Main Execution ---
# The main execution block is removed to convert this file into a library module.
# The functionality will be invoked from the main server or a dedicated script.