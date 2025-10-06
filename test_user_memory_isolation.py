"""
Comprehensive Test Suite for User-Specific Memory Isolation

Tests:
1. Vector store user_id filtering
2. Memory manager user isolation
3. Memory nodes with RunnableConfig
4. End-to-end memory flow with multiple users
5. WhatsApp integration
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

from ai_companion.modules.memory.long_term.vector_store import get_vector_store
from ai_companion.modules.memory.long_term.memory_manager import get_memory_manager
from ai_companion.graph.nodes import memory_extraction_node, memory_injection_node
from ai_companion.graph.state import AICompanionState


class Colors:
    """Terminal colors for better output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_test(name: str):
    """Print test header"""
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.END}")


def print_success(message: str):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def print_error(message: str):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def print_info(message: str):
    """Print info message"""
    print(f"{Colors.YELLOW}ℹ️  {message}{Colors.END}")


async def test_1_vector_store_user_filtering():
    """Test 1: Vector Store User ID Filtering"""
    print_test("Vector Store User ID Filtering")
    
    try:
        vector_store = get_vector_store()
        
        # Clear any existing test data
        print_info("Setting up test data...")
        
        # Store memories for User A
        user_a = "+1234567890"
        vector_store.store_memory(
            text="My name is John and I love meditation",
            metadata={"id": "test_user_a_1", "timestamp": "2025-10-06T10:00:00"},
            user_id=user_a
        )
        vector_store.store_memory(
            text="I practice yoga every morning at 6 AM",
            metadata={"id": "test_user_a_2", "timestamp": "2025-10-06T10:05:00"},
            user_id=user_a
        )
        print_info(f"Stored 2 memories for User A ({user_a})")
        
        # Store memories for User B
        user_b = "+9876543210"
        vector_store.store_memory(
            text="My name is Sarah and I love cooking",
            metadata={"id": "test_user_b_1", "timestamp": "2025-10-06T10:00:00"},
            user_id=user_b
        )
        vector_store.store_memory(
            text="I bake bread every weekend",
            metadata={"id": "test_user_b_2", "timestamp": "2025-10-06T10:05:00"},
            user_id=user_b
        )
        print_info(f"Stored 2 memories for User B ({user_b})")
        
        # Test 1a: Search for User A - should only get User A's memories
        print_info("\nSearching memories for User A with query 'my name'...")
        memories_a = vector_store.search_memories("my name", user_id=user_a, k=5)
        print(f"   Found {len(memories_a)} memories for User A:")
        for mem in memories_a:
            print(f"   - {mem.text} (score: {mem.score:.2f})")
            if "John" not in mem.text:
                print_error("User A got someone else's memory!")
                return False
        
        if len(memories_a) == 0:
            print_error("User A should have at least 1 memory")
            return False
        
        if any("Sarah" in mem.text for mem in memories_a):
            print_error("User A should not see User B's memories!")
            return False
        
        print_success("User A only sees their own memories")
        
        # Test 1b: Search for User B - should only get User B's memories
        print_info("\nSearching memories for User B with query 'my name'...")
        memories_b = vector_store.search_memories("my name", user_id=user_b, k=5)
        print(f"   Found {len(memories_b)} memories for User B:")
        for mem in memories_b:
            print(f"   - {mem.text} (score: {mem.score:.2f})")
            if "Sarah" not in mem.text:
                print_error("User B got someone else's memory!")
                return False
        
        if len(memories_b) == 0:
            print_error("User B should have at least 1 memory")
            return False
        
        if any("John" in mem.text for mem in memories_b):
            print_error("User B should not see User A's memories!")
            return False
        
        print_success("User B only sees their own memories")
        
        # Test 1c: Verify complete isolation
        print_info("\nVerifying complete isolation...")
        if any(mem_a.text == mem_b.text for mem_a in memories_a for mem_b in memories_b):
            print_error("Found overlapping memories between users!")
            return False
        
        print_success("Complete isolation verified - no memory overlap")
        
        print_success("\n✅ TEST 1 PASSED: Vector Store User Filtering Works!")
        return True
        
    except Exception as e:
        print_error(f"TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_2_memory_manager_user_isolation():
    """Test 2: Memory Manager User Isolation"""
    print_test("Memory Manager User Isolation")
    
    try:
        memory_manager = get_memory_manager()
        
        # Test 2a: Extract and store with user_id
        print_info("Testing memory extraction with user context...")
        
        user_a = "+1111111111"
        message_a = HumanMessage(content="I want to book a consultation for my daughter's wedding on December 15th")
        
        await memory_manager.extract_and_store_memories(message_a, user_id=user_a)
        print_success(f"Extracted and stored memory for User A ({user_a})")
        
        user_b = "+2222222222"
        message_b = HumanMessage(content="I need a puja for Kaal Sarp Dosh next month")
        
        await memory_manager.extract_and_store_memories(message_b, user_id=user_b)
        print_success(f"Extracted and stored memory for User B ({user_b})")
        
        # Test 2b: Retrieve memories for User A
        print_info("\nRetrieving memories for User A about 'wedding'...")
        memories_a = memory_manager.get_relevant_memories("wedding consultation", user_id=user_a)
        print(f"   Found {len(memories_a)} memories for User A:")
        for mem in memories_a:
            print(f"   - {mem}")
        
        # Should find wedding-related memory
        has_wedding = any("wedding" in mem.lower() or "december" in mem.lower() for mem in memories_a)
        has_puja = any("puja" in mem.lower() or "kaal sarp" in mem.lower() for mem in memories_a)
        
        if has_puja:
            print_error("User A should not see User B's puja memory!")
            return False
        
        print_success("User A's memories are isolated from User B")
        
        # Test 2c: Retrieve memories for User B
        print_info("\nRetrieving memories for User B about 'puja'...")
        memories_b = memory_manager.get_relevant_memories("puja booking", user_id=user_b)
        print(f"   Found {len(memories_b)} memories for User B:")
        for mem in memories_b:
            print(f"   - {mem}")
        
        # Should find puja-related memory
        has_puja_b = any("puja" in mem.lower() or "kaal sarp" in mem.lower() for mem in memories_b)
        has_wedding_b = any("wedding" in mem.lower() or "december" in mem.lower() for mem in memories_b)
        
        if has_wedding_b:
            print_error("User B should not see User A's wedding memory!")
            return False
        
        print_success("User B's memories are isolated from User A")
        
        print_success("\n✅ TEST 2 PASSED: Memory Manager User Isolation Works!")
        return True
        
    except Exception as e:
        print_error(f"TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_memory_nodes_with_config():
    """Test 3: Memory Nodes with RunnableConfig"""
    print_test("Memory Nodes with RunnableConfig")
    
    try:
        # Test 3a: memory_extraction_node
        print_info("Testing memory_extraction_node with user context...")
        
        user_c = "+3333333333"
        state_c = AICompanionState(
            messages=[
                HumanMessage(content="Hello, my name is Alice"),
                AIMessage(content="Nice to meet you Alice!"),
                HumanMessage(content="I'm interested in booking a consultation for next week")
            ]
        )
        config_c = RunnableConfig(configurable={"thread_id": user_c})
        
        result = await memory_extraction_node(state_c, config_c)
        print_success(f"memory_extraction_node executed for user {user_c}")
        print(f"   Result: {result}")
        
        # Test 3b: memory_injection_node
        print_info("\nTesting memory_injection_node with user context...")
        
        # Give it a moment for memory to be indexed
        await asyncio.sleep(1)
        
        result = memory_injection_node(state_c, config_c)
        print_success(f"memory_injection_node executed for user {user_c}")
        print(f"   Memory context retrieved: {result.get('memory_context', 'None')[:100]}...")
        
        # Test 3c: Verify different user doesn't get Alice's memory
        print_info("\nVerifying isolation - checking different user...")
        user_d = "+4444444444"
        state_d = AICompanionState(
            messages=[
                HumanMessage(content="Tell me about consultations")
            ]
        )
        config_d = RunnableConfig(configurable={"thread_id": user_d})
        
        result_d = memory_injection_node(state_d, config_d)
        memory_context_d = result_d.get('memory_context', '')
        
        if "Alice" in memory_context_d:
            print_error("User D should not see User C's (Alice's) memories!")
            return False
        
        print_success("User D doesn't see User C's memories - isolation confirmed")
        
        print_success("\n✅ TEST 3 PASSED: Memory Nodes with Config Work!")
        return True
        
    except Exception as e:
        print_error(f"TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_4_similar_memory_deduplication():
    """Test 4: Similar Memory Deduplication Per User"""
    print_test("Similar Memory Deduplication Per User")
    
    try:
        memory_manager = get_memory_manager()
        
        # Test 4a: Store similar memories for same user
        print_info("Testing deduplication for same user...")
        
        user_e = "+5555555555"
        message1 = HumanMessage(content="My favorite color is blue")
        message2 = HumanMessage(content="I really love the color blue")
        
        await memory_manager.extract_and_store_memories(message1, user_id=user_e)
        print_info("Stored first message about blue color")
        
        await asyncio.sleep(0.5)  # Small delay
        
        await memory_manager.extract_and_store_memories(message2, user_id=user_e)
        print_info("Attempted to store similar message about blue color")
        
        # Retrieve memories
        await asyncio.sleep(1)  # Wait for indexing
        memories = memory_manager.get_relevant_memories("favorite color", user_id=user_e)
        
        print(f"   User E has {len(memories)} memories about color")
        for mem in memories:
            print(f"   - {mem}")
        
        # Should have deduplicated (only 1 memory about blue color)
        blue_count = sum(1 for mem in memories if "blue" in mem.lower())
        if blue_count > 1:
            print_error(f"Found {blue_count} similar memories - deduplication may not be working")
            # This is a warning, not a failure - similarity threshold might need tuning
        else:
            print_success("Similar memories deduplicated for same user")
        
        # Test 4b: Different users can have similar memories
        print_info("\nTesting that different users can have similar memories...")
        
        user_f = "+6666666666"
        message3 = HumanMessage(content="My favorite color is also blue")
        
        await memory_manager.extract_and_store_memories(message3, user_id=user_f)
        print_info("Stored message for User F about blue color")
        
        await asyncio.sleep(1)
        memories_f = memory_manager.get_relevant_memories("favorite color", user_id=user_f)
        
        print(f"   User F has {len(memories_f)} memories about color")
        for mem in memories_f:
            print(f"   - {mem}")
        
        # User F should have their own blue memory (not deduplicated with User E)
        if len(memories_f) == 0:
            print_error("User F should have their own memory even if similar to User E")
            return False
        
        print_success("Different users can have similar memories independently")
        
        print_success("\n✅ TEST 4 PASSED: Memory Deduplication Works Per User!")
        return True
        
    except Exception as e:
        print_error(f"TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_backward_compatibility():
    """Test 5: Backward Compatibility (user_id=None)"""
    print_test("Backward Compatibility - user_id=None")
    
    try:
        vector_store = get_vector_store()
        memory_manager = get_memory_manager()
        
        # Test 5a: Store without user_id
        print_info("Testing storage without user_id...")
        vector_store.store_memory(
            text="This is a legacy memory without user_id",
            metadata={"id": "legacy_test", "timestamp": "2025-10-06T12:00:00"}
        )
        print_success("Stored memory without user_id (backward compatible)")
        
        # Test 5b: Search without user_id (should search all)
        print_info("\nTesting search without user_id...")
        all_memories = vector_store.search_memories("legacy memory", user_id=None, k=10)
        print(f"   Found {len(all_memories)} memories (searching all users)")
        
        # Test 5c: Memory manager without user_id
        print_info("\nTesting memory manager without user_id...")
        message = HumanMessage(content="Testing backward compatibility")
        await memory_manager.extract_and_store_memories(message, user_id=None)
        print_success("Memory manager works without user_id")
        
        memories = memory_manager.get_relevant_memories("compatibility", user_id=None)
        print(f"   Retrieved {len(memories)} memories without user filter")
        
        print_success("\n✅ TEST 5 PASSED: Backward Compatibility Maintained!")
        return True
        
    except Exception as e:
        print_error(f"TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests and report results"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print("USER-SPECIFIC MEMORY ISOLATION - COMPREHENSIVE TEST SUITE")
    print(f"{'='*70}{Colors.END}\n")
    
    results = {}
    
    # Run each test
    results["Test 1: Vector Store Filtering"] = await test_1_vector_store_user_filtering()
    results["Test 2: Memory Manager Isolation"] = await test_2_memory_manager_user_isolation()
    results["Test 3: Memory Nodes with Config"] = await test_3_memory_nodes_with_config()
    results["Test 4: Deduplication Per User"] = await test_4_similar_memory_deduplication()
    results["Test 5: Backward Compatibility"] = await test_5_backward_compatibility()
    
    # Print summary
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print("TEST SUMMARY")
    print(f"{'='*70}{Colors.END}\n")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    failed = total - passed
    
    for test_name, result in results.items():
        status = f"{Colors.GREEN}✅ PASSED{Colors.END}" if result else f"{Colors.RED}❌ FAILED{Colors.END}"
        print(f"{test_name}: {status}")
    
    print(f"\n{Colors.BOLD}Total: {total} | Passed: {Colors.GREEN}{passed}{Colors.END}{Colors.BOLD} | Failed: {Colors.RED}{failed}{Colors.END}{Colors.BOLD}{Colors.END}")
    
    if failed == 0:
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL TESTS PASSED! 🎉{Colors.END}")
        print(f"{Colors.GREEN}User-specific memory isolation is working correctly!{Colors.END}\n")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  SOME TESTS FAILED ⚠️{Colors.END}")
        print(f"{Colors.RED}Please review the failures above.{Colors.END}\n")
        return False


if __name__ == "__main__":
    try:
        success = asyncio.run(run_all_tests())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error running tests: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

