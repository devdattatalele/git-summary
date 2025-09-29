#!/usr/bin/env python3
"""
Gemini API Quota Checker

A simple utility to test Gemini API access and quota status.
Run this before attempting repository ingestion to check if your quota is available.
"""

import os
import time
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import GoogleGenerativeAIEmbeddings

# Load environment variables
load_dotenv()

def check_gemini_quota():
    """Test Gemini API access and basic quota availability."""
    print("🔍 Checking Gemini API Quota Status...")
    print("=" * 50)
    
    # Check API key
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in environment")
        print("💡 Please add GOOGLE_API_KEY to your .env file")
        return False
    
    print(f"✅ API Key found: {api_key[:20]}...")
    
    try:
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Test embeddings client
        print("\n🧪 Testing Embeddings API...")
        embeddings = GoogleGenerativeAIEmbeddings(
            model="models/embedding-001", 
            google_api_key=api_key
        )
        
        # Test with minimal request
        test_text = "Hello, this is a test."
        start_time = time.time()
        
        try:
            result = embeddings.embed_query(test_text)
            duration = time.time() - start_time
            
            print(f"✅ SUCCESS: Embedding API working")
            print(f"   Response time: {duration:.2f}s")
            print(f"   Vector dimensions: {len(result) if result else 'Unknown'}")
            print(f"   Quota status: ✅ AVAILABLE")
            
            return True
            
        except Exception as e:
            error_str = str(e).lower()
            print(f"❌ EMBEDDING TEST FAILED: {e}")
            
            if "429" in error_str or "quota" in error_str or "rate limit" in error_str:
                print("🚨 QUOTA EXHAUSTED DETECTED!")
                print("")
                print("💡 SOLUTIONS:")
                print("   1. Wait 15+ minutes for quota reset")
                print("   2. Try again in a few hours")
                print("   3. Upgrade to Gemini Pro API for higher quotas")
                print("   4. Check your API key billing status")
                print("")
                print("📊 Free Tier Limits:")
                print("   • Text generation: 15 requests/minute, 1,500/day")
                print("   • Embeddings: Very limited on free tier")
                print("   • Quota resets: Usually hourly/daily")
                
            return False
            
    except Exception as e:
        print(f"❌ API Configuration failed: {e}")
        return False

def main():
    """Main function."""
    print("🤖 Gemini API Quota Checker")
    print("This tool helps diagnose quota issues before repository ingestion")
    print("")
    
    quota_available = check_gemini_quota()
    
    print("")
    print("=" * 50)
    
    if quota_available:
        print("🎉 QUOTA AVAILABLE - Safe to proceed with ingestion")
        print("")
        print("💡 NEXT STEPS:")
        print("   • Your Gemini API quota appears to be available")
        print("   • You can proceed with repository ingestion")
        print("   • Emergency mode will still use ultra-conservative settings")
        print("   • Expect ~45-60 seconds per chunk in emergency mode")
    else:
        print("⚠️ QUOTA ISSUES DETECTED - Wait before ingesting")
        print("")
        print("🕒 RECOMMENDED ACTIONS:")
        print("   1. Wait 15+ minutes for quota reset")
        print("   2. Run this script again to retest")
        print("   3. Consider upgrading to Gemini Pro API")
        print("   4. Try ingesting smaller repositories first")

if __name__ == "__main__":
    main()
