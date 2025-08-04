# Configuration

The project uses environment variables to manage sensitive API keys and other settings.

### 1. Create a `.env` File

Create a file named `.env` in the root of the project directory. You can copy the provided example file:

```bash
cp env_example.txt .env
```

### 2. Add Your API Keys

Open the `.env` file and add your credentials for the following services:

-   **`GOOGLE_API_KEY`**: Your API key for Google AI Studio (for Gemini).
-   **`GITHUB_TOKEN`**: A GitHub Personal Access Token with `repo` scopes.
-   **`GOOGLE_DOCS_ID`** (Optional): The ID of a Google Doc where analysis reports will be saved.

### 3. Google Docs API Credentials

If you want to use the Google Docs integration, you also need to set up OAuth 2.0 credentials.

1.  Follow the official Google guide to [create OAuth 2.0 credentials](https://developers.google.com/docs/api/quickstart/python#authorize_credentials_for_a_desktop_application) for a **Desktop app**.
2.  Download the `credentials.json` file and place it in the root of your project directory.
3.  The first time you run a command that uses the Google Docs API, you will be prompted to authorize the application in your browser. 