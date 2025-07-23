# ingest_repo.py

import os
import time
import argparse
import subprocess # <-- ADD THIS
import shutil     # <-- ADD THIS

from dotenv import load_dotenv
from github import Github, RateLimitExceededException
from pinecone import Pinecone, ServerlessSpec
from langchain.text_splitter import RecursiveCharacterTextSplitter
import google.generativeai as genai
from tqdm import tqdm

# --- CONFIGURATION ---
# Load environment variables from .env file
load_dotenv()

# Gemini model details. The 'embedding-001' is a powerful free model.
# Its output vectors have 768 dimensions.
GEMINI_EMBEDDING_MODEL = "models/embedding-001"
VECTOR_DIMENSION = 768

# Pinecone configuration
PINECONE_INDEX_NAME = "github-repo-knowledge-base"

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

        # Pinecone - Initialize with new API
        pinecone_api_key = os.getenv("PINECONE_API_KEY")
        if not pinecone_api_key:
            raise ValueError("PINECONE_API_KEY not found in .env file")
        
        print(f"Initializing Pinecone...")
        pc = Pinecone(api_key=pinecone_api_key)

        return g, pc
    except Exception as e:
        print(f"Error during client initialization: {e}")
        exit()

def get_or_create_pinecone_index(pc: Pinecone):
    """Checks if a Pinecone index exists, and if not, creates it."""
    available_indexes = [index.name for index in pc.list_indexes()]
    if PINECONE_INDEX_NAME not in available_indexes:
        print(f"Pinecone index '{PINECONE_INDEX_NAME}' not found. Creating a new serverless index...")
        # Create serverless index for free tier
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=VECTOR_DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )
        print("Serverless index created successfully. It might take a moment to be ready.")
        time.sleep(60) # Give the index time to initialize
    return pc.Index(PINECONE_INDEX_NAME)

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
def chunk_and_embed_and_upsert(documents, index):
    """Chunks documents, creates embeddings, and upserts to Pinecone."""
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    
    batch_size = 100 # Gemini API has a limit on requests per minute
    total_vectors_upserted = 0
    
    for i in tqdm(range(0, len(documents), batch_size), desc="Processing documents in batches"):
        batch_docs = documents[i:i + batch_size]
        
        all_chunks = []
        metadata_list = []
        
        # 1. Chunking
        for doc in batch_docs:
            chunks = text_splitter.split_text(doc["content"])
            for chunk in chunks:
                all_chunks.append(chunk)
                metadata_list.append({
                    "source": doc["source"],
                    "type": doc["type"],
                    "text": chunk # Store the original text in metadata
                })
        
        if not all_chunks:
            continue

        # 2. Embedding
        try:
            result = genai.embed_content(
                model=GEMINI_EMBEDDING_MODEL,
                content=all_chunks,
                task_type="RETRIEVAL_DOCUMENT",
                title="GitHub Repository Knowledge" # Optional but can improve embeddings
            )
            embeddings = result['embedding']
        except Exception as e:
            print(f"An error occurred during embedding: {e}")
            # Potentially add a retry mechanism here
            continue
            
        # 3. Upserting to Pinecone
        if embeddings:
            vectors_to_upsert = []
            for j, embedding in enumerate(embeddings):
                # Create a unique ID for each vector
                vector_id = f"{metadata_list[j]['source'].replace('/', '-')}-chunk-{i+j}"
                vectors_to_upsert.append({
                    "id": vector_id,
                    "values": embedding,
                    "metadata": metadata_list[j]
                })

            index.upsert(vectors=vectors_to_upsert)
            total_vectors_upserted += len(vectors_to_upsert)
    
    print(f"Finished. Total vectors upserted to Pinecone: {total_vectors_upserted}")


# --- MAIN EXECUTION ---
def main():
    parser = argparse.ArgumentParser(description="Ingest a GitHub repository's docs and issues into a Pinecone index.")
    parser.add_argument("repo_name", type=str, help="The GitHub repository in 'owner/repo' format.")
    args = parser.parse_args()

    print("--- Starting GitHub Knowledge Base Ingestion ---")
    
    github_client, pinecone_client = initialize_clients()
    
    try:
        repo = github_client.get_repo(args.repo_name)
        print(f"Successfully connected to repository: {repo.full_name}")
    except Exception as e:
        print(f"Could not access repository {args.repo_name}. Check the name and your GITHUB_TOKEN. Error: {e}")
        return

    # Get or create the Pinecone index
    pinecone_index = get_or_create_pinecone_index(pinecone_client)
    
    # Fetch all data - using the faster local clone method
    docs = fetch_repo_docs(repo.full_name)
    issues = fetch_repo_issues(repo)
    all_documents = docs + issues

    if not all_documents:
        print("No documents or issues found to process. Exiting.")
        return

    # Process and store in Pinecone
    chunk_and_embed_and_upsert(all_documents, pinecone_index)
    
    print("--- Ingestion Complete ---")
    # You can check the index stats in the Pinecone console
    print(pinecone_index.describe_index_stats())

if __name__ == "__main__":
    main()