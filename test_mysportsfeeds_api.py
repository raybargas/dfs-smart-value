#!/usr/bin/env python3
"""
Test script for MySportsFeeds API connection.
Run this to diagnose API issues.

Usage:
    python test_mysportsfeeds_api.py
"""

import os
import sys
from dotenv import load_dotenv
import requests
from requests.auth import HTTPBasicAuth
import json

# Load environment variables
load_dotenv()

def test_api_connection():
    """Test MySportsFeeds API connection and injury endpoint."""
    
    print("=" * 70)
    print("MySportsFeeds API Connection Test")
    print("=" * 70)
    print()
    
    # Check for API key
    api_key = os.getenv('MYSPORTSFEEDS_API_KEY')
    if not api_key:
        print("❌ ERROR: MYSPORTSFEEDS_API_KEY not found in .env file")
        print()
        print("Please create a .env file with:")
        print("MYSPORTSFEEDS_API_KEY=your_api_key_here")
        print()
        return False
    
    print(f"✓ API Key found: {api_key[:10]}...{api_key[-4:]}")
    print()
    
    # Test the injuries endpoint
    print("Testing injuries endpoint...")
    print("-" * 70)
    
    url = "https://api.mysportsfeeds.com/v2.1/pull/nfl/injuries.json"
    params = {
        'force': 'true'  # Force fresh content
    }
    
    print(f"URL: {url}")
    print(f"Params: {params}")
    print(f"Auth: HTTP Basic Auth (username=API_KEY, password=MYSPORTSFEEDS)")
    print()
    
    try:
        # Make the request
        print("Sending request...")
        response = requests.get(
            url,
            params=params,
            auth=HTTPBasicAuth(api_key, "MYSPORTSFEEDS"),
            timeout=10
        )
        
        print(f"Response Status: {response.status_code}")
        print()
        
        # Handle different status codes
        if response.status_code == 200:
            print("✅ SUCCESS! API connection working.")
            print()
            
            # Parse response
            data = response.json()
            injuries = data.get('injuries', [])
            
            print(f"Total injuries found: {len(injuries)}")
            print()
            
            if injuries:
                print("Sample injury data (first 3 players):")
                print("-" * 70)
                for i, injury in enumerate(injuries[:3], 1):
                    player = injury.get('player', {})
                    first_name = player.get('firstName', '')
                    last_name = player.get('lastName', '')
                    team = player.get('currentTeam', {}).get('abbreviation', 'N/A')
                    status = injury.get('playingProbability', 'UNKNOWN')
                    body_part = injury.get('description', 'N/A')
                    
                    print(f"{i}. {first_name} {last_name} ({team})")
                    print(f"   Status: {status}")
                    print(f"   Injury: {body_part}")
                    print()
                
                print("✅ Full response structure:")
                print(json.dumps(injuries[0], indent=2))
            else:
                print("⚠️  No injuries found (this might be normal if no players are injured)")
            
            return True
            
        elif response.status_code == 401:
            print("❌ AUTHENTICATION FAILED (401)")
            print()
            print("Possible causes:")
            print("- Invalid API key")
            print("- API key not activated")
            print()
            print("Solution:")
            print("1. Check your API key at https://www.mysportsfeeds.com/account/")
            print("2. Make sure you copied it correctly to your .env file")
            print()
            return False
            
        elif response.status_code == 403:
            print("❌ ACCESS FORBIDDEN (403)")
            print()
            print("⚠️  YOUR SUBSCRIPTION DOES NOT INCLUDE THE REQUIRED 'DETAILED' ADDON")
            print()
            print("The injuries endpoint requires the DETAILED addon to be active.")
            print()
            print("Solution:")
            print("1. Visit https://www.mysportsfeeds.com/account/")
            print("2. Check your subscription plan")
            print("3. Add the 'DETAILED' addon if not included")
            print("4. Consider upgrading your plan if needed")
            print()
            return False
            
        elif response.status_code == 429:
            print("❌ RATE LIMIT EXCEEDED (429)")
            print()
            print("You've made too many requests. Wait and try again later.")
            print()
            return False
            
        else:
            print(f"❌ ERROR: Unexpected status code {response.status_code}")
            print()
            print("Response body:")
            print(response.text[:500])
            print()
            return False
            
    except requests.exceptions.Timeout:
        print("❌ REQUEST TIMEOUT")
        print()
        print("The request took too long. Check your internet connection.")
        print()
        return False
        
    except requests.exceptions.RequestException as e:
        print(f"❌ NETWORK ERROR: {e}")
        print()
        return False
        
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_api_connection()
    print()
    print("=" * 70)
    
    if success:
        print("✅ Test completed successfully!")
        print()
        print("Your MySportsFeeds API is configured correctly.")
        print("You can now use the Narrative Intelligence tab in the app.")
        sys.exit(0)
    else:
        print("❌ Test failed. Please fix the issues above.")
        print()
        print("Need help? Check API_SETUP.md for detailed setup instructions.")
        sys.exit(1)

