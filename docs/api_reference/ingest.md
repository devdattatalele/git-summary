# Ingest API

The `issue_solver.ingest` module contains functions for building the repository knowledge base.

### `fetch_repo_code(repo_full_name: str)`

Clones a repository and extracts code files, chunking them at the function/class level.

-   **Arguments:**
    -   `repo_full_name` (str): The repository name in `owner/repo` format.
-   **Returns:** A list of dictionaries, where each dictionary is a code chunk.

### `fetch_repo_docs(repo_full_name: str)`

Clones a repository and extracts all Markdown and text files.

-   **Arguments:**
    -   `repo_full_name` (str): The repository name in `owner/repo` format.
-   **Returns:** A list of dictionaries, where each dictionary is a document.

### `fetch_repo_issues(repo)`

Fetches all open and closed issues from the repository.

-   **Arguments:**
    -   `repo`: A `github.Repository` object.
-   **Returns:** A list of dictionaries, where each dictionary is an issue.

### `fetch_repo_pr_history(repo)`

Fetches merged pull request history with diffs.

-   **Arguments:**
    -   `repo`: A `github.Repository` object.
-   **Returns:** A list of dictionaries, where each dictionary is a pull request.

### `chunk_and_embed_and_store(documents, embeddings, collection_name: str)`

Chunks documents, creates embeddings, and stores them in the specified Chroma collection.

-   **Arguments:**
    -   `documents` (list): A list of document dictionaries to process.
    -   `embeddings`: An initialized LangChain embeddings model.
    -   `collection_name` (str): The name of the Chroma collection to store the data in.
-   **Returns:** The total number of documents stored. 