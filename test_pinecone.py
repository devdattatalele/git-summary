#!/usr/bin/env python3
"""
Test script to check Pinecone connection and available options
"""

import os
import pinecone
from dotenv import load_dotenv

load_dotenv()

pinecone_api_key = os.getenv("PINECONE_API_KEY")
if not pinecone_api_key:
    print("PINECONE_API_KEY not found in .env file")
    exit(1)

print("Testing Pinecone connection...")

try:
    # Initialize Pinecone
    pinecone.init(api_key=pinecone_api_key)
    print("✅ Successfully connected to Pinecone")
    
    # List existing indexes
    indexes = pinecone.list_indexes()
    print(f"📋 Available indexes: {indexes}")
    
    # Try to get account information
    print("📊 Testing account capabilities...")
    
    try:
        # Try creating a simple test index to see what's supported
        test_index_name = "test-connection"
        
        if test_index_name not in indexes:
            print(f"🔄 Attempting to create test index '{test_index_name}'...")
            
            # Try without any spec first (default)
            try:
                pinecone.create_index(
                    name=test_index_name,
                    dimension=8,  # Small dimension for testing
                    metric="cosine"
                )
                print("✅ Successfully created default index")
                
                # Clean up
                pinecone.delete_index(test_index_name)
                print("🧹 Cleaned up test index")
                
            except Exception as e:
                print(f"❌ Default index creation failed: {e}")
                
                # Check if it mentions serverless
                if "serverless" in str(e).lower():
                    print("💡 Your account might require serverless indexes")
                elif "pod" in str(e).lower():
                    print("💡 Your account might have pod limitations")
                    
        else:
            print(f"ℹ️ Test index already exists")
            
    except Exception as e:
        print(f"❌ Error testing account capabilities: {e}")
        
except Exception as e:
    print(f"❌ Failed to connect to Pinecone: {e}")
    print("🔍 Please check your PINECONE_API_KEY in the .env file")

print("\n📝 To find your exact environment, visit:")
print("   https://app.pinecone.io/ > Project Settings > Environment")
print("\n💡 For free tier accounts, you typically need:")
print("   - No environment parameter (newer accounts)")
print("   - Or specific environment like 'gcp-starter' (older accounts)") 