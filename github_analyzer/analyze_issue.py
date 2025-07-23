# analyze_issue.py
import os
import re
import json
import argparse
from datetime import datetime
from dotenv import load_dotenv

from github import Github
from pinecone import Pinecone
# --- LangChain Imports ---
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain.agents import AgentExecutor, create_react_agent
from langchain.tools.retriever import create_retriever_tool
from langchain_core.prompts import ChatPromptTemplate

# --- Google Docs API Imports ---
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Configuration ---
load_dotenv()

# Load API keys from .env file
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
GOOGLE_DOCS_ID = os.getenv("GOOGLE_DOCS_ID")

# Validate required environment variables
required_vars = {
    'GOOGLE_API_KEY': GOOGLE_API_KEY,
    'PINECONE_API_KEY': PINECONE_API_KEY,
    'GITHUB_TOKEN': GITHUB_TOKEN,
    'PINECONE_INDEX_NAME': PINECONE_INDEX_NAME,
    'GOOGLE_DOCS_ID': GOOGLE_DOCS_ID
}

for var_name, var_value in required_vars.items():
    if not var_value:
        raise ValueError(f"Required environment variable {var_name} is not set in .env file")

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
    print(f"Fetching issue '{owner}/{repo_name}#{issue_number}' from GitHub...")
    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(number=issue_number)
        return issue
    except Exception as e:
        raise Exception(f"Failed to fetch GitHub issue: {e}")

def initialize_pinecone_retriever():
    """Initializes the Pinecone vector store and retriever tool."""
    print("Initializing Pinecone vector store and retriever...")
    try:
        # Initialize Pinecone with new API
        print(f"Initializing Pinecone...")
        pc = Pinecone(api_key=PINECONE_API_KEY)
        
        # Check if the index exists
        available_indexes = [index.name for index in pc.list_indexes()]
        if PINECONE_INDEX_NAME not in available_indexes:
            raise ValueError(
                f"Pinecone index '{PINECONE_INDEX_NAME}' not found. "
                f"Available indexes: {available_indexes}. "
                f"Please run the ingestion script first."
            )
        
        # Connect to the specific index
        pinecone_index = pc.Index(PINECONE_INDEX_NAME)
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=GOOGLE_API_KEY)
        
        # Use the standard langchain-pinecone integration
        vector_store = PineconeVectorStore(
            index=pinecone_index,
            embedding=embeddings,
            text_key="text"
        )
        
        retriever = vector_store.as_retriever(search_kwargs={"k": 5})
        
        # This creates the tool the agent can use
        tool = create_retriever_tool(
            retriever,
            "github_knowledge_base_search",
            "Search the knowledge base for relevant past issues and documentation. Use this to find context for a new GitHub issue.",
        )
        return tool
    except Exception as e:
        raise Exception(f"Failed to initialize Pinecone retriever: {e}")

def create_langchain_agent(issue):
    """Creates and runs the LangChain agent to analyze the issue."""
    print("Initializing LangChain Agent...")
    try:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest", temperature=0.2, google_api_key=GOOGLE_API_KEY)
        retriever_tool = initialize_pinecone_retriever()
        tools = [retriever_tool]

        # Enhanced prompt template with better instructions
        prompt_template = """
        You are an expert AI assistant for the '{repo_full_name}' repository.
        Your task is to analyze a new GitHub issue using the context retrieved from the knowledge base.

        You have access to the following tools:
        {tools}

        Use the following format:

        Question: the input question you must answer
        Thought: you should always think about what to do
        Action: the action to take, should be one of [{tool_names}]
        Action Input: the input to the action
        Observation: the result of the action
        ... (this Thought/Action/Action Input/Observation can repeat N times)
        Thought: I now know the final answer
        Final Answer: the final answer to the original input question

        First, use the 'github_knowledge_base_search' tool to search for any documentation or past issues that are relevant to the new issue's title and body. Search multiple times with different keywords if needed to get comprehensive context.

        Based on the new issue and the retrieved context, provide a comprehensive analysis.
        
        IMPORTANT: Your Final Answer MUST be a valid JSON object with exactly these keys:
        1. "summary": A concise, one-sentence summary of the user's problem.
        2. "proposed_solution": A detailed step-by-step technical plan to solve the issue. If the context contains a similar solved issue, reference it and adapt the solution. Use newline characters for formatting.
        3. "complexity": An integer from 1 to 5 (1=Trivial, 5=Very Complex).
        4. "similar_issues": An array of strings containing the source of any relevant past issues from the context (e.g., ["issue #123", "issue #456"]). If no relevant issues are found, return an empty array [].

        New Issue Details:
        - Repository: {repo_full_name}
        - Title: {issue_title}
        - Body: {issue_body}
        - Issue URL: {issue_url}

        Question: Please analyze this GitHub issue and provide a comprehensive analysis in JSON format.
        {agent_scratchpad}
        """
        
        prompt = ChatPromptTemplate.from_template(prompt_template)
        
        agent = create_react_agent(llm, tools, prompt)
        agent_executor = AgentExecutor(
            agent=agent, 
            tools=tools, 
            verbose=True,
            max_iterations=10,
            handle_parsing_errors=True
        )

        print("Running agent to analyze issue...")
        response = agent_executor.invoke({
            "repo_full_name": issue.repository.full_name,
            "issue_title": issue.title,
            "issue_body": issue.body or "No body provided.",
            "issue_url": issue.html_url
        })
        
        return response['output']
    except Exception as e:
        raise Exception(f"Failed to run LangChain agent: {e}")

def parse_agent_output(raw_output: str):
    """Extracts and parses the JSON from the agent's raw output string."""
    print("Parsing agent's JSON output...")
    try:
        # Try to find JSON block within ```json ... ```
        match = re.search(r"```json\s*\n([\s\S]*?)\n\s*```", raw_output)
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)
        
        # Try to find JSON block within ``` ... ```
        match = re.search(r"```\s*\n([\s\S]*?)\n\s*```", raw_output)
        if match:
            json_str = match.group(1).strip()
            return json.loads(json_str)
        
        # Try to find JSON object directly
        match = re.search(r"(\{[\s\S]*\})", raw_output)
        if match:
            json_str = match.group(1)
            return json.loads(json_str)
        
        # Fallback - try to parse the entire output as JSON
        return json.loads(raw_output)
        
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        print(f"Raw output was: {raw_output}")
        # Return a default structure
        return {
            "summary": "Could not parse agent response",
            "proposed_solution": "Please review the raw agent output manually",
            "complexity": 3,
            "similar_issues": []
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
        
        print("Appending analysis to Google Doc...")
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
        print("Successfully updated Google Doc.")
    except Exception as e:
        print(f"An error occurred while updating Google Docs: {e}")
        print("The analysis will be printed to console instead:")
        print(text_to_append)

# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(description="Analyze a GitHub issue and summarize it in a Google Doc.")
    parser.add_argument("issue_url", type=str, help="The full URL of the GitHub issue to analyze.")
    args = parser.parse_args()

    try:
        print("--- Starting GitHub Issue Analysis ---")
        
        # 1. Get Issue Details
        owner, repo, issue_number = parse_github_url(args.issue_url)
        issue = get_github_issue(owner, repo, issue_number)
        
        print(f"Analyzing issue: {issue.title}")
        print(f"Repository: {issue.repository.full_name}")

        # 2. Run Agent to get Analysis
        agent_raw_output = create_langchain_agent(issue)
        
        # 3. Parse the output
        analysis = parse_agent_output(agent_raw_output)
        
        # 4. Format the final report
        report_text = f"""---
### Issue #{issue.number}: {issue.title}
- **Repository:** {issue.repository.full_name}
- **Link:** {issue.html_url}
- **Analyzed On:** {datetime.now().strftime('%d %B, %Y at %H:%M')}
- **Status:** {issue.state}

| Category            | AI Analysis                                                  |
| ------------------- | ------------------------------------------------------------ |
| **Summary**         | {analysis.get('summary', 'N/A')}                             |
| **Complexity**      | {analysis.get('complexity', 'N/A')} / 5                      |
| **Similar Issues**  | {', '.join(analysis.get('similar_issues', [])) or 'None Found'} |

**Proposed Solution:**
{analysis.get('proposed_solution', 'N/A')}

---

"""

        # 5. Append to Google Doc
        append_to_google_doc(report_text)
        
        print("--- Analysis Complete ---")
        print(f"Issue #{issue.number} has been analyzed and documented.")

    except Exception as e:
        print(f"An error occurred during the process: {e}")
        return 1

if __name__ == "__main__":
    exit(main())