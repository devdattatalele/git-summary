# GitHub Issue Analyzer

An AI-powered system that analyzes GitHub issues using retrieval-augmented generation (RAG). The system ingests repository documentation and historical issues into a vector database, then uses LangChain agents with Google Gemini AI to provide intelligent analysis of new issues. **Phase 2** now includes automatic patch generation and PR creation.

## 🎯 What This System Does

### **Phase 1: Knowledge Ingestion (`ingest_repo.py`)**
- Clones GitHub repositories locally for fast access
- Extracts documentation files (`.md`, `.txt`, `README`)
- Fetches all repository issues (open and closed) with comments
- **NEW**: Extracts and analyzes code at function/class level
- **NEW**: Ingests PR history with diffs for learning from past solutions
- Chunks content for optimal embedding
- Creates vector embeddings using Google Gemini
- **NEW**: Stores everything in Pinecone vector database with organized namespaces:
  - `documentation`: Repository docs and README files
  - `issues_history`: Historical issues and comments
  - `repo_code_main`: Function-level code chunks with metadata
  - `pr_history`: Merged PR diffs and descriptions

### **Phase 2: Issue Analysis (`analyze_issue.py`)**
- Takes a GitHub issue URL as input
- Uses LangChain agents to search the knowledge base
- Finds similar past issues and relevant documentation
- Provides AI analysis including:
  - Problem summary
  - Complexity assessment (1-5 scale)
  - Step-by-step solution proposal
  - References to similar resolved issues
- **NEW**: Automatically generates code patches by querying:
  - PR history for similar solutions
  - Repository code for relevant functions/files
- **NEW**: Creates draft PRs with generated patches (for low-complexity issues)
- Automatically writes comprehensive analysis to Google Docs

### **Phase 3: Patch Generation (`patch_generator.py`)**
- **NEW**: Queries multiple Pinecone namespaces for comprehensive context
- **NEW**: Uses LLM to generate unified diff patches
- **NEW**: Automatically creates GitHub branches and applies patches
- **NEW**: Opens draft PRs with detailed change summaries
- **NEW**: Configurable complexity thresholds for auto-PR creation

## 🏗️ Architecture

```
GitHub Repo → Local Clone → Text/Code Extraction → Function Parsing → Gemini Embeddings → Pinecone Namespaces
                                                                                              ↓
                                                                           ┌─ documentation ─┐
                                                                           ├─ issues_history ─┤
                                                                           ├─ repo_code_main ─┤
                                                                           └─ pr_history ─────┘
                                                                                              ↓
New Issue URL → GitHub API → LangChain Agent → Multi-Namespace Search → Gemini Analysis → Patch Generator
                                                                                              ↓
                                                                           Google Docs ← Draft PR ← GitHub API
```

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
# Install compatible Pinecone SDK
pip install pinecone-client==2.2.4

# Install all dependencies (including new GitPython)
pip install python-dotenv PyGithub langchain-google-genai langchain-pinecone langchain google-generativeai tqdm google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client GitPython
```

### 2. Set Up API Keys

Copy `env_example.txt` to `.env` and fill in your credentials:

```bash
cp env_example.txt .env
```

**Required API Keys:**

1. **GitHub Token**: Generate at https://github.com/settings/tokens
   - For public repos: `public_repo` scope
   - **For patch generation**: `repo` scope (required for creating branches and PRs)

2. **Google API Key**: Get from https://console.cloud.google.com/apis/credentials
   - Enable Generative AI API
   - Create API key

3. **Pinecone API Key**: Get from https://app.pinecone.io/
   - Create a free account
   - Copy your API key

4. **Google Docs ID**: Create a Google Doc and extract ID from URL
   - URL format: `https://docs.google.com/document/d/{DOCUMENT_ID}/edit`

**NEW Phase 2 Configuration:**

5. **ENABLE_PATCH_GENERATION**: Set to `true` to enable automatic patch generation
6. **MAX_COMPLEXITY_FOR_AUTO_PR**: Set threshold (1-5) for auto-creating PRs

### 3. Set Up Google Docs API (Optional but Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Docs API
4. Create credentials (OAuth 2.0)
5. Download `credentials.json` to your project root

## 📖 Usage

### Step 1: Ingest Repository Knowledge (Enhanced)

```bash
cd github-rag-ingestion
python ingest_repo.py "owner/repo-name"
```

**NEW Options:**
```bash
# Skip PR history for faster ingestion
python ingest_repo.py "owner/repo-name" --skip-prs

# Skip code analysis for docs-only projects  
python ingest_repo.py "owner/repo-name" --skip-code
```

**Example:**
```bash
python ingest_repo.py "microsoft/vscode"
```

This will:
- Clone the repository locally
- Extract all documentation
- **NEW**: Parse code files and extract functions/classes
- Fetch all issues and comments
- **NEW**: Fetch merged PR history with diffs
- Create vector embeddings
- **NEW**: Store in organized Pinecone namespaces

### Step 2: Analyze Issues with Patch Generation

```bash
cd github_analyzer
python analyze_issue.py "https://github.com/owner/repo/issues/123"
```

**NEW Options:**
```bash
# Skip patch generation for analysis-only
python analyze_issue.py "https://github.com/owner/repo/issues/123" --no-patches
```

**Example:**
```bash
python analyze_issue.py "https://github.com/microsoft/vscode/issues/12345"
```

This will:
- Fetch the issue details
- Search vector database for relevant context
- Generate AI analysis
- **NEW**: Generate code patches using AI
- **NEW**: Automatically create draft PR (if complexity ≤ threshold)
- Write comprehensive results to Google Docs

## 📊 Example Output (Enhanced)

The analysis now includes patch generation results:

```
### Issue #123: Login Button Not Working
- Repository: owner/repo-name
- Link: https://github.com/owner/repo/issues/123
- Analyzed On: 15 January, 2025 at 14:30
- Status: open

| Category            | AI Analysis                                    |
| ------------------- | ---------------------------------------------- |
| Summary             | Login button click handler is not attached    |
| Complexity          | 2 / 5                                         |
| Similar Issues      | PR #45, issue #78                             |

Proposed Solution:
1. Add click event listener to login button
2. Implement authentication validation
3. Add error handling for failed login attempts
4. Update UI state based on authentication status

Patch Generation Results:
- Auto-generated PR: https://github.com/owner/repo/pull/124
- Files Modified: 2
- Summary of Changes: Added event listener and validation logic to LoginComponent
```

## 🔧 Technical Details

### **Technologies Used:**
- **Pinecone**: Vector database for semantic search with namespace organization
- **Google Gemini**: AI embeddings and text generation
- **LangChain**: Agent framework and RAG pipeline
- **PyGithub**: GitHub API integration
- **GitPython**: Git operations for patch application
- **Google Docs API**: Automated report generation

### **NEW: Namespace Organization:**
```json
{
  "documentation": "README files, docs, markdown",
  "issues_history": "Past issues and comments",
  "repo_code_main": "Function-level code chunks", 
  "pr_history": "Merged PR diffs and descriptions"
}
```

### **NEW: Enhanced Metadata Schema:**
```json
{
  "code_chunk": {
    "filePath": "src/components/Login.tsx",
    "functionName": "handleLogin", 
    "functionType": "function",
    "branch": "main",
    "start_line": 45,
    "end_line": 67
  },
  "pr_chunk": {
    "pr_number": 123,
    "pr_title": "Fix login validation",
    "pr_url": "https://github.com/...",
    "merged_at": "2025-01-15T10:30:00Z"
  }
}
```

### **NEW: Patch Generation Pipeline:**
1. **Context Retrieval**: Query `pr_history` and `repo_code_main` namespaces
2. **LLM Analysis**: Generate unified diff patches using contextual information
3. **Branch Creation**: Create new Git branch via GitHub API
4. **Patch Application**: Apply patches to files using GitPython
5. **PR Creation**: Open draft PR with detailed change summary

### **Why pinecone-client==2.2.4?**
The latest Pinecone SDK (v3+) changed the API completely and is not compatible with LangChain integrations. Version 2.2.4 is the last compatible version.

## 🛠️ Troubleshooting

### Common Issues:

1. **Import Error: cannot import name 'Pinecone'**
   ```bash
   pip uninstall pinecone pinecone-client -y
   pip install pinecone-client==2.2.4
   ```

2. **Patch Generation Import Error**
   - Ensure `patch_generator.py` is in the project root
   - Check Python path configuration in `analyze_issue.py`

3. **GitHub Permission Error for PR Creation**
   - Ensure GitHub token has `repo` scope (not just `public_repo`)
   - Verify repository write permissions

4. **Empty Namespaces**
   - Run ingestion script with appropriate flags
   - Check Pinecone dashboard for namespace statistics

5. **Function Parsing Errors**
   - Supported languages: Python, JavaScript, TypeScript
   - Files that can't be parsed fall back to whole-file chunks

## 🔮 Future Enhancements

- [x] **Function-level code analysis**
- [x] **PR history ingestion and learning**
- [x] **Automatic patch generation**
- [x] **Draft PR creation**
- [ ] Support for more programming languages in function extraction
- [ ] Advanced patch conflict resolution
- [ ] Multi-repository knowledge bases
- [ ] Slack/Discord integration for notifications
- [ ] Custom analysis templates
- [ ] Automated issue triage and labeling
- [ ] Integration with project management tools
- [ ] Code review automation

## 📝 License

This project is open source. Feel free to modify and adapt for your needs.

---

**Built with ❤️ for better GitHub issue management and automated patch generation** 

