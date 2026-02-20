#!/usr/bin/env python3
"""
Runtime Demo - Test runtime capture (Case B)

This script demonstrates runtime metadata capture:
1. Create client
2. Set runtime metadata (provider, model, mode)
3. Track tool events
4. Flush - should inject runtime_info event
5. Flush again - should NOT inject runtime_info (idempotent)

Prerequisites:
- Set environment variables:
  export SURFA_API_URL="http://localhost:3000"
  export SURFA_INGEST_KEY="sk_live_..."
  
- Ensure Next.js dev server is running

Run with: python examples/runtime_demo.py
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
    print("Surfa Ingest SDK - Runtime Capture Demo")
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
        flush_at=10,
    )
    print(f"   ✓ Session ID: {client.session_id}")
    
    # Set runtime metadata
    print("\n2️⃣  Setting runtime metadata...")
    client.set_runtime(
        provider="anthropic",
        model="claude-sonnet-4-5",
        mode="messages",
        extra={
            "temperature": 0.7,
            "max_tokens": 4096,
        },
        api_version="2023-06-01",  # Additional kwarg
    )
    print("   ✓ Runtime set:")
    print(f"      • Provider: anthropic")
    print(f"      • Model: claude-sonnet-4-5")
    print(f"      • Mode: messages")
    print(f"      • Temperature: 0.7")
    print(f"      • Max Tokens: 4096")
    print(f"      • API Version: 2023-06-01")
    print(f"   ✓ Runtime info will be emitted on next flush")
    
    # Track session start
    print("\n3️⃣  Tracking session start...")
    client.session_start()
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Track tool call
    print("\n4️⃣  Tracking tool call...")
    client.tool_started(
        tool_name="search_web",
        args={"query": "AI runtime tracking"}
    )
    client.tool_completed(
        tool_name="search_web",
        result={"count": 3},
        latency_ms=156
    )
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # First flush - should inject runtime_info
    print("\n5️⃣  First flush (should inject runtime_info)...")
    print(f"   → Sending {len(client._buffer)} events + runtime_info...")
    
    try:
        response = client.flush()
        
        if response:
            print("\n✅ Flush successful!")
            print(f"\n📦 Response:")
            print(f"   • Inserted Count: {response.get('inserted_count', 'N/A')}")
            print(f"   • Execution ID: {response.get('execution_id', 'N/A')}")
            
            # Should have inserted 3 events + 1 runtime_info = 4 total
            expected_count = 4  # runtime_info + session_start + tool_started + tool_completed
            actual_count = response.get('inserted_count', 0)
            
            if actual_count == expected_count:
                print(f"\n   ✅ Correct count: {actual_count} events")
                print(f"      (1 runtime_info + 3 tracked events)")
            else:
                print(f"\n   ⚠️  Expected {expected_count} events, got {actual_count}")
            
            execution_id = response.get('execution_id')
            
        else:
            print("\n⚠️  No events to flush")
            sys.exit(1)
        
    except Exception as e:
        print(f"\n❌ Flush failed: {e}")
        sys.exit(1)
    
    # Track another event
    print("\n6️⃣  Tracking another tool call...")
    client.tool_started(
        tool_name="write_file",
        args={"path": "/tmp/test.txt"}
    )
    print(f"   ✓ Buffer size: {len(client._buffer)}")
    
    # Second flush - should NOT inject runtime_info (already emitted)
    print("\n7️⃣  Second flush (should NOT inject runtime_info)...")
    print(f"   → Sending {len(client._buffer)} events (no runtime_info)...")
    
    try:
        response2 = client.flush()
        
        if response2:
            print("\n✅ Flush successful!")
            print(f"\n📦 Response:")
            print(f"   • Inserted Count: {response2.get('inserted_count', 'N/A')}")
            
            # Should have inserted only 1 event (no runtime_info)
            expected_count = 1
            actual_count = response2.get('inserted_count', 0)
            
            if actual_count == expected_count:
                print(f"\n   ✅ Correct count: {actual_count} event")
                print(f"      (runtime_info NOT re-emitted - idempotent!)")
            else:
                print(f"\n   ⚠️  Expected {expected_count} event, got {actual_count}")
        
    except Exception as e:
        print(f"\n❌ Second flush failed: {e}")
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)
    
    print("\n💡 Verify in database:")
    print(f"""
    SELECT seq, kind, subtype, tool_name, 
           payload->>'provider' as provider,
           payload->>'model' as model,
           payload->>'mode' as mode
    FROM events
    WHERE execution_id = '{execution_id}'
    ORDER BY seq ASC;
    """)
    
    print("\n📊 Expected results:")
    print("   seq=1: kind=runtime, subtype=runtime_info")
    print("          provider=anthropic, model=claude-sonnet-4-5")
    print("   seq=2: kind=session, subtype=session_started")
    print("   seq=3: kind=tool, subtype=call_started, tool_name=search_web")
    print("   seq=4: kind=tool, subtype=call_completed, tool_name=search_web")
    print("   seq=5: kind=tool, subtype=call_started, tool_name=write_file")
    print()


if __name__ == "__main__":
    main()
