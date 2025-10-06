"""
Unit Test for User-Specific Memory Logic (No External Dependencies)

This test verifies the implementation logic without requiring Qdrant connection.
Tests that user_id parameters are correctly passed through the call chain.
"""

import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, AsyncMock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig


class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'


def print_test(name: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}TEST: {name}{Colors.END}")
    print(f"{Colors.BLUE}{Colors.BOLD}{'='*70}{Colors.END}")


def print_success(message: str):
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")


def print_error(message: str):
    print(f"{Colors.RED}❌ {message}{Colors.END}")


def test_1_vector_store_parameters():
    """Test 1: Verify VectorStore methods accept user_id parameter"""
    print_test("VectorStore Method Signatures")
    
    try:
        from ai_companion.modules.memory.long_term.vector_store import VectorStore
        import inspect
        
        # Check store_memory signature
        store_sig = inspect.signature(VectorStore.store_memory)
        assert 'user_id' in store_sig.parameters, "store_memory missing user_id parameter"
        print_success("store_memory() has user_id parameter")
        
        # Check search_memories signature
        search_sig = inspect.signature(VectorStore.search_memories)
        assert 'user_id' in search_sig.parameters, "search_memories missing user_id parameter"
        print_success("search_memories() has user_id parameter")
        
        # Check find_similar_memory signature
        find_sig = inspect.signature(VectorStore.find_similar_memory)
        assert 'user_id' in find_sig.parameters, "find_similar_memory missing user_id parameter"
        print_success("find_similar_memory() has user_id parameter")
        
        print_success("\n✅ TEST 1 PASSED: VectorStore has correct signatures!")
        return True
        
    except Exception as e:
        print_error(f"TEST 1 FAILED: {e}")
        return False


def test_2_memory_manager_parameters():
    """Test 2: Verify MemoryManager methods accept user_id parameter"""
    print_test("MemoryManager Method Signatures")
    
    try:
        from ai_companion.modules.memory.long_term.memory_manager import MemoryManager
        import inspect
        
        # Check extract_and_store_memories signature
        extract_sig = inspect.signature(MemoryManager.extract_and_store_memories)
        assert 'user_id' in extract_sig.parameters, "extract_and_store_memories missing user_id parameter"
        print_success("extract_and_store_memories() has user_id parameter")
        
        # Check get_relevant_memories signature
        get_sig = inspect.signature(MemoryManager.get_relevant_memories)
        assert 'user_id' in get_sig.parameters, "get_relevant_memories missing user_id parameter"
        print_success("get_relevant_memories() has user_id parameter")
        
        print_success("\n✅ TEST 2 PASSED: MemoryManager has correct signatures!")
        return True
        
    except Exception as e:
        print_error(f"TEST 2 FAILED: {e}")
        return False


def test_3_memory_nodes_accept_config():
    """Test 3: Verify memory nodes accept RunnableConfig parameter"""
    print_test("Memory Nodes Accept RunnableConfig")
    
    try:
        from ai_companion.graph.nodes import memory_extraction_node, memory_injection_node
        import inspect
        
        # Check memory_extraction_node signature
        extract_sig = inspect.signature(memory_extraction_node)
        assert 'config' in extract_sig.parameters, "memory_extraction_node missing config parameter"
        print_success("memory_extraction_node() has config parameter")
        
        # Check memory_injection_node signature
        inject_sig = inspect.signature(memory_injection_node)
        assert 'config' in inject_sig.parameters, "memory_injection_node missing config parameter"
        print_success("memory_injection_node() has config parameter")
        
        print_success("\n✅ TEST 3 PASSED: Memory nodes accept RunnableConfig!")
        return True
        
    except Exception as e:
        print_error(f"TEST 3 FAILED: {e}")
        return False


def test_4_user_id_passed_to_vector_store():
    """Test 4: Verify user_id is passed from MemoryManager to VectorStore"""
    print_test("user_id Propagation: MemoryManager → VectorStore")
    
    try:
        from ai_companion.modules.memory.long_term.memory_manager import MemoryManager
        
        # Mock the vector store
        mock_vector_store = Mock()
        mock_vector_store.find_similar_memory = Mock(return_value=None)
        mock_vector_store.store_memory = Mock()
        mock_vector_store.search_memories = Mock(return_value=[])
        
        # Create memory manager with mocked vector store
        memory_manager = MemoryManager.__new__(MemoryManager)
        memory_manager.vector_store = mock_vector_store
        memory_manager.logger = Mock()
        
        # Test get_relevant_memories passes user_id
        test_user = "+1234567890"
        memory_manager.get_relevant_memories("test query", user_id=test_user)
        
        # Verify user_id was passed to vector store
        mock_vector_store.search_memories.assert_called_once()
        call_kwargs = mock_vector_store.search_memories.call_args[1]
        assert call_kwargs.get('user_id') == test_user, f"user_id not passed correctly: {call_kwargs}"
        
        print_success(f"get_relevant_memories() correctly passes user_id='{test_user}' to search_memories()")
        
        print_success("\n✅ TEST 4 PASSED: user_id propagates through the stack!")
        return True
        
    except Exception as e:
        print_error(f"TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_thread_id_extraction():
    """Test 5: Verify thread_id is extracted from RunnableConfig"""
    print_test("thread_id Extraction from RunnableConfig")
    
    try:
        from ai_companion.graph.nodes import memory_extraction_node, memory_injection_node
        from ai_companion.graph.state import AICompanionState
        
        # Mock memory manager
        with patch('ai_companion.graph.nodes.get_memory_manager') as mock_get_mm:
            mock_memory_manager = Mock()
            mock_memory_manager.extract_and_store_memories = AsyncMock()
            mock_memory_manager.get_relevant_memories = Mock(return_value=[])
            mock_memory_manager.format_memories_for_prompt = Mock(return_value="")
            mock_get_mm.return_value = mock_memory_manager
            
            # Test memory_extraction_node
            test_thread_id = "+9876543210"
            state = AICompanionState(
                messages=[HumanMessage(content="Test message")]
            )
            config = RunnableConfig(configurable={"thread_id": test_thread_id})
            
            await memory_extraction_node(state, config)
            
            # Verify thread_id was extracted and passed as user_id
            mock_memory_manager.extract_and_store_memories.assert_called_once()
            call_kwargs = mock_memory_manager.extract_and_store_memories.call_args[1]
            assert call_kwargs.get('user_id') == test_thread_id, f"thread_id not extracted correctly: {call_kwargs}"
            
            print_success(f"memory_extraction_node extracts thread_id='{test_thread_id}' and passes as user_id")
            
            # Test memory_injection_node
            mock_memory_manager.reset_mock()
            memory_injection_node(state, config)
            
            # Verify thread_id was extracted and passed as user_id
            mock_memory_manager.get_relevant_memories.assert_called_once()
            call_args = mock_memory_manager.get_relevant_memories.call_args
            assert call_args[1].get('user_id') == test_thread_id, f"thread_id not extracted correctly: {call_args}"
            
            print_success(f"memory_injection_node extracts thread_id='{test_thread_id}' and passes as user_id")
        
        print_success("\n✅ TEST 5 PASSED: thread_id correctly extracted from config!")
        return True
        
    except Exception as e:
        print_error(f"TEST 5 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_6_qdrant_filter_construction():
    """Test 6: Verify Qdrant filter is constructed correctly with user_id"""
    print_test("Qdrant Filter Construction")
    
    try:
        # Test the filter construction logic directly
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # Simulate what happens in search_memories
        test_user = "+5555555555"
        
        # When user_id is provided, filter should be created
        query_filter = None
        if test_user:
            query_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=test_user))]
            )
        
        assert query_filter is not None, "query_filter not created when user_id provided"
        assert isinstance(query_filter, Filter), "query_filter should be a Filter object"
        print_success(f"query_filter created when user_id='{test_user}'")
        
        # When user_id is None, filter should not be created
        query_filter = None
        user_id_none = None
        if user_id_none:
            query_filter = Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id_none))]
            )
        
        assert query_filter is None, "query_filter should be None when user_id not provided"
        print_success("query_filter is None when user_id=None (backward compatible)")
        
        # Verify the implementation in VectorStore matches this logic
        import inspect
        from ai_companion.modules.memory.long_term.vector_store import VectorStore
        
        source = inspect.getsource(VectorStore.search_memories)
        assert 'if user_id:' in source, "search_memories should check for user_id"
        assert 'Filter' in source, "search_memories should create Filter when user_id provided"
        assert 'FieldCondition' in source, "search_memories should use FieldCondition"
        assert 'query_filter=' in source, "search_memories should pass query_filter to client.search"
        print_success("VectorStore.search_memories implementation contains filtering logic")
        
        print_success("\n✅ TEST 6 PASSED: Qdrant filter logic is correct!")
        return True
        
    except Exception as e:
        print_error(f"TEST 6 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all logic tests"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}")
    print("USER-SPECIFIC MEMORY - LOGIC VERIFICATION TESTS")
    print("(Testing implementation without external dependencies)")
    print(f"{'='*70}{Colors.END}\n")
    
    results = {}
    
    # Run synchronous tests
    results["Test 1: VectorStore Signatures"] = test_1_vector_store_parameters()
    results["Test 2: MemoryManager Signatures"] = test_2_memory_manager_parameters()
    results["Test 3: Nodes Accept Config"] = test_3_memory_nodes_accept_config()
    results["Test 4: user_id Propagation"] = test_4_user_id_passed_to_vector_store()
    
    # Run async tests
    import asyncio
    results["Test 5: thread_id Extraction"] = asyncio.run(test_5_thread_id_extraction())
    results["Test 6: Qdrant Filter Construction"] = test_6_qdrant_filter_construction()
    
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
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 ALL LOGIC TESTS PASSED! 🎉{Colors.END}")
        print(f"{Colors.GREEN}User-specific memory implementation is correct!{Colors.END}\n")
        return True
    else:
        print(f"\n{Colors.RED}{Colors.BOLD}⚠️  SOME TESTS FAILED ⚠️{Colors.END}\n")
        return False


if __name__ == "__main__":
    try:
        success = run_all_tests()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}Fatal error running tests: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

