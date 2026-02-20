#!/usr/bin/env python3
"""
Flush Demo - Test HTTP flush functionality

This script demonstrates the complete flow:
1. Create client with API key
2. Track session start
3. Track tool events
4. Flush to API
5. Print response

Prerequisites:
- Set environment variables:
  export SURFA_API_URL="http://localhost:3000"
  export SURFA_INGEST_KEY="sk_live_..."
  
- Ensure Next.js dev server is running

Run with: python examples/flush_demo.py
"""

import os
import sys
import json
from pathlib import Path

# Add parent directory to path for local imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from surfa_ingest import SurfaClient


def main():
    print("=" * 60)
    print("Surfa Ingest SDK - Flush Demo")
    print("=" * 60)
    
    # Get configuration from environment
    api_url = os.getenv("SURFA_API_URL")
    ingest_key = os.getenv("SURFA_INGEST_KEY")
    
    if not api_url:
        print("\n❌ Error: SURFA_API_URL environment variable not set")
        print("   Run: export SURFA_API_URL='http://localhost:3000'")
        sys.exit(1)
    
    if not ingest_key:
        print("\n❌ Error: SURFA_INGEST_KEY environment variable not set")
        print("   Run: export SURFA_INGEST_KEY='sk_live_...'")
        sys.exit(1)
    
    print(f"\n📡 API URL: {api_url}")
    print(f"🔑 API Key: {ingest_key[:20]}...")
    
    # Create client
    print("\n1️⃣  Creating client...")
    client = SurfaClient(
        ingest_key=ingest_key,
        api_url=api_url,
        flush_at=10,  # Auto-flush after 10 events
        timeout_s=10,
    )
    print(f"   ✓ Session ID: {client.session_id}")
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Set runtime metadata
    print("\n2️⃣  Setting runtime metadata...")
    client.set_runtime(
        provider="anthropic",
        model="claude-sonnet-4-5",
        mode="messages",
    )
    print("   ✓ Runtime metadata set")
    
    # Track session start
    print("\n3️⃣  Tracking session start...")
    client.session_start()
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Track tool call started
    print("\n4️⃣  Tracking tool call started...")
    client.tool_started(
        tool_name="search_web",
        args={
            "query": "Python SDK best practices",
            "limit": 10,
        }
    )
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Track tool call completed
    print("\n5️⃣  Tracking tool call completed...")
    client.tool_completed(
        tool_name="search_web",
        result={
            "count": 5,
            "results": ["Result 1", "Result 2", "Result 3"],
        },
        latency_ms=234,
    )
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Track custom event
    print("\n6️⃣  Tracking custom event...")
    client.custom_event(
        subtype="demo_event",
        message="Hello from flush demo!",
        version="0.1.0",
    )
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Flush to API
    print("\n7️⃣  Flushing events to API...")
    print(f"   → Sending {len(client._buffer)} events...")
    
    try:
        response = client.flush()
        
        if response:
            print("\n✅ Flush successful!")
            print("\n📦 Response:")
            print(json.dumps(response, indent=2))
            
            # Show key fields
            print("\n📊 Summary:")
            print(f"   • Workspace ID: {response.get('workspace_id', 'N/A')}")
            print(f"   • Execution ID: {response.get('execution_id', 'N/A')}")
            print(f"   • Execution Status: {response.get('execution_status', 'N/A')}")
            print(f"   • Inserted Count: {response.get('inserted_count', 'N/A')}")
            print(f"   • Correlation Normalized: {response.get('correlation_normalized', 'N/A')}")
            
            # Show stored execution_id
            print(f"\n💾 Stored execution_id: {client.execution_id}")
            print(f"   (Will be reused for next flush)")
            
        else:
            print("\n⚠️  No events to flush (buffer was empty)")
        
    except Exception as e:
        print(f"\n❌ Flush failed: {e}")
        sys.exit(1)
    
    # Verify buffer is cleared
    print(f"\n8️⃣  Verifying buffer cleared...")
    print(f"   ✓ Buffer size: {len(client._buffer)} (should be 0)")
    
    # Track one more event and flush again (should reuse execution_id)
    print("\n9️⃣  Testing execution_id reuse...")
    client.tool_started(
        tool_name="write_file",
        args={"path": "/tmp/test.txt", "content": "Hello!"}
    )
    print(f"   ✓ Added 1 more event")
    print(f"   → Flushing with execution_id={client.execution_id}...")
    
    try:
        response2 = client.flush()
        if response2:
            print(f"   ✓ Execution ID: {response2.get('execution_id')}")
            print(f"   ✓ Same as before: {response2.get('execution_id') == client.execution_id}")
    except Exception as e:
        print(f"   ❌ Second flush failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)
    
    print("\n💡 Next steps:")
    print("   1. Check the database:")
    print("      SELECT kind, subtype, tool_name, ts")
    print("      FROM events")
    print("      ORDER BY created_at DESC")
    print("      LIMIT 20;")
    print()
    print("   2. View in Surfa UI:")
    print(f"      http://localhost:3000/executions/{client.execution_id}")
    print()


if __name__ == "__main__":
    main()
