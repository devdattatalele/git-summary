# GitHub Issue Analyzer

An AI-powered system that analyzes GitHub issues using retrieval-augmented generation (RAG). The system ingests repository documentation and historical issues into a vector database, then uses LangChain agents with Google Gemini AI to provide intelligent analysis of new issues.

## 🎯 What This System Does

### **Phase 1: Knowledge Ingestion (`ingest_repo.py`)**
- Clones GitHub repositories locally for fast access
- Extracts documentation files (`.md`, `.txt`, `README`)
- Fetches all repository issues (open and closed) with comments
- Chunks content for optimal embedding
- Creates vector embeddings using Google Gemini
- Stores everything in Pinecone vector database

### **Phase 2: Issue Analysis (`analyze_issue.py`)**
- Takes a GitHub issue URL as input
- Uses LangChain agents to search the knowledge base
- Finds similar past issues and relevant documentation
- Provides AI analysis including:
  - Problem summary
  - Complexity assessment (1-5 scale)
  - Step-by-step solution proposal
  - References to similar resolved issues
- Automatically writes analysis to Google Docs

## 🏗️ Architecture

```
GitHub Repo → Local Clone → Text Extraction → Chunking → Gemini Embeddings → Pinecone Vector DB
                                                                                        ↓
New Issue URL → GitHub API → LangChain Agent → Vector Search → Gemini Analysis → Google Docs
```

## 🚀 Setup Instructions

### 1. Install Dependencies

```bash
# Install compatible Pinecone SDK
pip install pinecone-client==2.2.4

# Install other dependencies
pip install python-dotenv PyGithub langchain-google-genai langchain-pinecone langchain google-generativeai tqdm google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. Set Up API Keys

Copy `env_example.txt` to `.env` and fill in your credentials:

```bash
cp env_example.txt .env
```

**Required API Keys:**

1. **GitHub Token**: Generate at https://github.com/settings/tokens
   - For public repos: `public_repo` scope
   - For private repos: `repo` scope

2. **Google API Key**: Get from https://console.cloud.google.com/apis/credentials
   - Enable Generative AI API
   - Create API key

3. **Pinecone API Key**: Get from https://app.pinecone.io/
   - Create a free account
   - Copy your API key

4. **Google Docs ID**: Create a Google Doc and extract ID from URL
   - URL format: `https://docs.google.com/document/d/{DOCUMENT_ID}/edit`

### 3. Set Up Google Docs API (Optional but Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google Docs API
4. Create credentials (OAuth 2.0)
5. Download `credentials.json` to your project root

## 📖 Usage

### Step 1: Ingest Repository Knowledge

```bash
cd github-rag-ingestion
python ingest_repo.py "owner/repo-name"
```

**Example:**
```bash
python ingest_repo.py "microsoft/vscode"
```

This will:
- Clone the repository locally
- Extract all documentation
- Fetch all issues and comments
- Create vector embeddings
- Store in Pinecone (index created automatically)

### Step 2: Analyze New Issues

```bash
cd github_analyzer
python analyze_issue.py "https://github.com/owner/repo/issues/123"
```

**Example:**
```bash
python analyze_issue.py "https://github.com/microsoft/vscode/issues/12345"
```

This will:
- Fetch the issue details
- Search vector database for relevant context
- Generate AI analysis
- Write results to Google Docs

## 📊 Example Output

The analysis includes:

```
### Issue #123: Feature Request: Dark Mode Toggle
- Repository: owner/repo-name
- Link: https://github.com/owner/repo/issues/123
- Analyzed On: 15 January, 2025 at 14:30
- Status: open

| Category            | AI Analysis                                    |
| ------------------- | ---------------------------------------------- |
| Summary             | User requests dark mode toggle in settings    |
| Complexity          | 3 / 5                                         |
| Similar Issues      | issue #45, issue #78                          |

Proposed Solution:
1. Add theme state management to settings store
2. Create toggle component in settings UI
3. Update CSS variables based on theme
4. Add system preference detection
5. Persist user choice in localStorage
```

## 🔧 Technical Details

### **Technologies Used:**
- **Pinecone**: Vector database for semantic search
- **Google Gemini**: AI embeddings and text generation
- **LangChain**: Agent framework and RAG pipeline
- **PyGithub**: GitHub API integration
- **Google Docs API**: Automated report generation

### **Why pinecone-client==2.2.4?**
The latest Pinecone SDK (v3+) changed the API completely and is not compatible with LangChain integrations. Version 2.2.4 is the last compatible version.

### **Vector Database Schema:**
```json
{
  "id": "source-chunk-123",
  "values": [0.1, 0.2, ...], // 768-dimensional embedding
  "metadata": {
    "source": "README.md" | "issue #123",
    "type": "doc" | "issue",
    "text": "original chunk text"
  }
}
```

## 🛠️ Troubleshooting

### Common Issues:

1. **Import Error: cannot import name 'Pinecone'**
   ```bash
   pip uninstall pinecone pinecone-client -y
   pip install pinecone-client==2.2.4
   ```

2. **Google Docs Permission Error**
   - Ensure `credentials.json` is in project root
   - Run the script once to authenticate
   - Share the Google Doc with your Google account

3. **Pinecone Index Not Found**
   - Run the ingestion script first
   - Check your `PINECONE_INDEX_NAME` in `.env`

4. **GitHub Rate Limit**
   - Use a GitHub token with appropriate permissions
   - For large repos, the local clone method is used automatically

## 🔮 Future Enhancements

- [ ] Support for pull request analysis
- [ ] Multi-repository knowledge bases
- [ ] Slack/Discord integration
- [ ] Custom analysis templates
- [ ] Automated issue triage
- [ ] Integration with project management tools

## 📝 License

This project is open source. Feel free to modify and adapt for your needs.

---

**Built with ❤️ for better GitHub issue management** 

