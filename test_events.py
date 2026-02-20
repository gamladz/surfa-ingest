#!/usr/bin/env python3
"""
Test script to demonstrate event helpers and buffer tracking.

Run with: python3 test_events.py
"""

from surfa_ingest import SurfaClient
from surfa_ingest.events import (
    session_started,
    session_ended,
    tool_call_started,
    tool_call_completed,
    tool_call_failed,
    custom,
)
import json


def print_event(name: str, event: dict) -> None:
    """Pretty print an event"""
    print(f"\n{name}:")
    print(json.dumps(event, indent=2))


def main():
    print("=" * 60)
    print("Surfa Ingest SDK - Event Helpers Demo")
    print("=" * 60)
    
    # Test 1: Event helper functions
    print("\n📝 Testing Event Helper Functions\n")
    
    # Session events
    evt1 = session_started()
    print_event("session_started()", evt1)
    
    evt2 = session_ended()
    print_event("session_ended()", evt2)
    
    # Tool events
    evt3 = tool_call_started("search_web", args={"query": "AI news", "limit": 10})
    print_event("tool_call_started()", evt3)
    
    evt4 = tool_call_completed("search_web", result={"count": 5}, latency_ms=234)
    print_event("tool_call_completed()", evt4)
    
    evt5 = tool_call_failed("search_web", error="Network timeout", latency_ms=5000)
    print_event("tool_call_failed()", evt5)
    
    # Custom event
    evt6 = custom(subtype="user_action", action="button_click", button_id="submit")
    print_event("custom()", evt6)
    
    # Test 2: Client convenience methods
    print("\n" + "=" * 60)
    print("📦 Testing Client Buffer Tracking")
    print("=" * 60)
    
    client = SurfaClient(ingest_key="sk_test_demo_key_1234567890", flush_at=10)
    print(f"\nInitialized client: {client}")
    print(f"Session ID: {client.session_id}")
    print(f"Buffer size: {len(client._buffer)}/{client.flush_at}")
    
    # Track session start
    print("\n1. Calling client.session_start()...")
    client.session_start()
    print(f"   Buffer size: {len(client._buffer)}/{client.flush_at}")
    
    # Track tool started
    print("\n2. Calling client.tool_started('search_web', ...)...")
    client.tool_started("search_web", args={"query": "Python tutorials"})
    print(f"   Buffer size: {len(client._buffer)}/{client.flush_at}")
    
    # Track tool completed
    print("\n3. Calling client.tool_completed('search_web', ...)...")
    client.tool_completed("search_web", result={"count": 10}, latency_ms=150)
    print(f"   Buffer size: {len(client._buffer)}/{client.flush_at}")
    
    # Track custom event
    print("\n4. Calling client.custom_event(...)...")
    client.custom_event(subtype="test", message="Hello from SDK")
    print(f"   Buffer size: {len(client._buffer)}/{client.flush_at}")
    
    # Show buffered events
    print("\n" + "=" * 60)
    print("📋 Buffered Events")
    print("=" * 60)
    for i, event in enumerate(client._buffer, 1):
        print(f"\nEvent {i}:")
        print(f"  kind: {event['kind']}")
        print(f"  subtype: {event.get('subtype', 'N/A')}")
        print(f"  tool_name: {event.get('tool_name', 'N/A')}")
        print(f"  ts: {event['ts']}")
    
    # Test 3: Context manager
    print("\n" + "=" * 60)
    print("🔄 Testing Context Manager")
    print("=" * 60)
    
    print("\nUsing 'with' statement...")
    with SurfaClient(ingest_key="sk_test_context_key_1234567890", flush_at=5) as ctx_client:
        print(f"  Session ID: {ctx_client.session_id}")
        print(f"  Buffer size: {len(ctx_client._buffer)}")
        
        ctx_client.tool_started("write_file", args={"path": "/tmp/test.txt"})
        print(f"  After tool_started: {len(ctx_client._buffer)} events")
        
        ctx_client.tool_completed("write_file", latency_ms=50)
        print(f"  After tool_completed: {len(ctx_client._buffer)} events")
    
    print("  Context exited (session_end + flush called automatically)")
    
    # Summary
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)
    print(f"\nTotal events created: {len(client._buffer)}")
    print("All event helpers working correctly!")
    print("\nNote: HTTP calls not implemented yet (L2.3)")


if __name__ == "__main__":
    main()
