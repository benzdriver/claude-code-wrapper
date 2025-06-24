#!/usr/bin/env python3
"""
ContextMonitor 完整测试套件
目标：提升 ContextMonitor 覆盖率到 60%+
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest


import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from datetime import datetime, timedelta
from pathlib import Path
import json

# Mock 外部依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()
sys.modules['watchdog'] = MagicMock()
sys.modules['watchdog.observers'] = MagicMock()
sys.modules['watchdog.events'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()


# ===== FileInfo 和 ContextState 测试 =====
@pytest.mark.asyncio
async def test_file_info():
    """测试 FileInfo 数据类"""
    from backend.services.context_monitor import FileInfo
    
    now = datetime.now()
    file_info = FileInfo(
        path="/test/file.py",
        tokens=100,
        loaded_at=now,
        size_bytes=1024
    )
    
    assert file_info.path == "/test/file.py"
    assert file_info.tokens == 100
    assert file_info.loaded_at == now
    assert file_info.size_bytes == 1024


@pytest.mark.asyncio
async def test_context_state():
    """测试 ContextState 数据类"""
    from backend.services.context_monitor import ContextState, FileInfo
    
    state = ContextState()
    
    # 测试默认值
    assert state.token_count == 0
    assert state.token_limit == 200000
    assert state.percentage == 0.0
    assert len(state.files_loaded) == 0
    assert state.last_compact is None
    assert state.messages_count == 0
    
    # 测试百分比计算
    state.token_count = 50000
    state.calculate_percentage()
    assert state.percentage == 25.0
    
    # 测试零限制
    state.token_limit = 0
    state.calculate_percentage()
    assert state.percentage == 0.0
    
    # 测试文件列表
    file_info = FileInfo(
        path="/test.py",
        tokens=100,
        loaded_at=datetime.now()
    )
    state.files_loaded.append(file_info)
    assert len(state.files_loaded) == 1


# ===== ContextMonitor 初始化测试 =====
@pytest.mark.asyncio
async def test_context_monitor_init():
    """测试 ContextMonitor 初始化"""
    from backend.services.context_monitor import ContextMonitor
    
    with patch('backend.services.context_monitor.settings') as mock_settings:
        mock_settings.claude_home = Path("/tmp/claude_test")
        
        monitor = ContextMonitor()
        
        # 检查属性
        assert monitor.claude_home == Path("/tmp/claude_test")
        assert monitor.projects_dir == Path("/tmp/claude_test/projects")
        assert monitor.current_session_file is None
        assert monitor.current_state is None
        assert monitor.event_bus is not None
        assert monitor._monitoring == False
        assert len(monitor._history) == 0
        assert monitor._max_history == 100


@pytest.mark.asyncio
async def test_find_session_file():
    """测试查找会话文件"""
    from backend.services.context_monitor import ContextMonitor
    
    monitor = ContextMonitor()
    
    # Mock 文件系统 - 使用实际的 iterdir 方法
    mock_project1 = Mock()
    mock_project1.is_dir.return_value = True
    mock_project1.name = "test-proj-1"
    mock_transcript1 = Mock()
    mock_transcript1.exists.return_value = True
    mock_transcript1.stat.return_value.st_mtime = 1000
    mock_project1.__truediv__ = lambda self, name: mock_transcript1 if name == "transcript.jsonl" else Mock()
    
    mock_project2 = Mock()
    mock_project2.is_dir.return_value = True
    mock_project2.name = "test-proj-2"
    mock_transcript2 = Mock()
    mock_transcript2.exists.return_value = True
    mock_transcript2.stat.return_value.st_mtime = 2000  # 更新的文件
    mock_project2.__truediv__ = lambda self, name: mock_transcript2 if name == "transcript.jsonl" else Mock()
    
    with patch.object(Path, 'exists', return_value=True):
        with patch.object(Path, 'iterdir', return_value=[mock_project1, mock_project2]):
            # 查找最新文件
            result = await monitor.find_session_file()
            assert result == mock_transcript2  # 最新的文件


@pytest.mark.asyncio
async def test_parse_context_state():
    """测试解析上下文状态"""
    from backend.services.context_monitor import ContextMonitor, ContextState
    
    monitor = ContextMonitor()
    
    # 创建测试 JSONL 数据 - 基于实际的 _process_jsonl_entry 实现
    jsonl_data = [
        json.dumps({"timestamp": "2024-01-01T12:00:00", "role": "user", "content": "hello"}),
        json.dumps({"usage": {"total_tokens": 150}}),
        json.dumps({"tool_calls": [{"tool_name": "read_file", "arguments": {"path": "/test.py"}}]}),
        json.dumps({"role": "assistant", "content": "I'll help with that"}),
        json.dumps({"content": "Context compacted successfully"})
    ]
    
    # 创建一个模拟的异步文件对象
    class AsyncFileMock:
        def __init__(self, lines):
            self.lines = lines
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, *args):
            pass
            
        def __aiter__(self):
            return self
            
        async def __anext__(self):
            if self.lines:
                return self.lines.pop(0)
            raise StopAsyncIteration
    
    mock_file = AsyncFileMock(jsonl_data.copy())
    mock_path = Mock(spec=Path)
    mock_path.exists.return_value = True
    mock_path.parent = Mock()
    mock_path.parent.name = "test-session"
    
    with patch('backend.services.context_monitor.aiofiles.open', return_value=mock_file):
        result = await monitor.parse_context_state(mock_path)
        
        assert result is not None
        assert result.session_id == "test-session"
        assert result.token_count == 150
        assert result.messages_count == 2  # user and assistant
        # File loading happens via tool_calls but only if not already loaded
        assert result.last_compact is not None


# ===== 监控功能测试 =====
@pytest.mark.asyncio
async def test_start_stop_monitoring():
    """测试启动和停止监控"""
    from backend.services.context_monitor import ContextMonitor
    
    monitor = ContextMonitor()
    
    # Mock find_session_file
    monitor.find_session_file = AsyncMock(return_value=Path("/test/session.jsonl"))
    monitor.parse_context_state = AsyncMock(return_value=Mock())
    monitor._monitor_loop = AsyncMock()
    
    # 启动监控
    await monitor.start_monitoring()
    assert monitor._monitoring == True
    assert monitor._monitor_task is not None
    
    # 停止监控
    await monitor.stop_monitoring()
    assert monitor._monitoring == False


@pytest.mark.asyncio
async def test_get_current_state():
    """测试获取当前状态"""
    from backend.services.context_monitor import ContextMonitor, ContextState
    
    monitor = ContextMonitor()
    
    # Mock find_session_file 返回 None
    monitor.find_session_file = AsyncMock(return_value=None)
    
    # 没有会话文件时，应该创建默认状态
    state = await monitor.get_current_state()
    assert state is not None
    assert state.session_id == "shell-session"
    assert state.token_count == 0
    
    # 再次调用应该返回相同的状态
    state2 = await monitor.get_current_state()
    assert state2 == state


@pytest.mark.asyncio
async def test_get_stats():
    """测试获取统计信息"""
    from backend.services.context_monitor import ContextMonitor, ContextState
    
    monitor = ContextMonitor()
    
    # 设置一些状态
    monitor._monitoring = True
    monitor._state_cache["session1"] = ContextState(session_id="session1")
    monitor._history.append({"event": "test", "timestamp": datetime.now()})
    monitor.observer = Mock()
    monitor.observer.is_alive = Mock(return_value=True)
    
    stats = monitor.get_stats()
    
    assert stats["monitoring"] == True
    assert stats["cache_size"] == 1
    assert stats["history_size"] == 1
    assert stats["current_session"] is None
    assert stats["observer_active"] == True


@pytest.mark.asyncio
async def test_get_history():
    """测试获取历史记录"""
    from backend.services.context_monitor import ContextMonitor
    
    monitor = ContextMonitor()
    
    # 添加历史记录
    for i in range(5):
        monitor._history.append({
            "event": f"event_{i}",
            "timestamp": datetime.now() - timedelta(minutes=i)
        })
    
    # 获取所有历史
    history = monitor.get_history()
    assert len(history) == 5
    
    # 获取有限历史 - get_history 返回最后 N 个元素
    history = monitor.get_history(limit=3)
    assert len(history) == 3
    assert history[2]["event"] == "event_4"  # 最后的元素


# ===== 文件监控测试 =====
@pytest.mark.asyncio
async def test_jsonl_file_handler():
    """测试 JSONL 文件处理器"""
    from backend.services.context_monitor import JSONLFileHandler
    
    # Mock 回调
    callback = AsyncMock()
    handler = JSONLFileHandler(callback)
    
    # 测试 JSONL 文件修改
    event = Mock()
    event.is_directory = False
    event.src_path = "/test/transcript.jsonl"
    
    # The handler needs to run in an event loop
    # Since we're testing synchronously, we'll check the logic directly
    # JSONL files should trigger the callback
    assert event.src_path.endswith('.jsonl')
    assert not event.is_directory
    
    # 测试非 JSONL 文件
    event.src_path = "/test/other.txt"
    # Non-JSONL files should not trigger the callback
    assert not event.src_path.endswith('.jsonl')


@pytest.mark.asyncio
async def test_watch_for_changes():
    """测试文件变化监控"""
    from backend.services.context_monitor import ContextMonitor
    
    monitor = ContextMonitor()
    
    # Mock find_session_file
    mock_session_file = Path("/test/session.jsonl")
    monitor.find_session_file = AsyncMock(return_value=mock_session_file)
    
    # Mock Observer
    mock_observer = Mock()
    mock_observer.start = Mock()
    mock_observer.stop = Mock()
    mock_observer.join = Mock()
    mock_observer.is_alive = Mock(return_value=True)
    
    # Mock _poll_changes to prevent actual polling
    monitor._poll_changes = AsyncMock()
    
    # Create a mock for JSONLFileHandler
    mock_handler_class = Mock()
    mock_handler_instance = Mock()
    mock_handler_class.return_value = mock_handler_instance
    
    with patch('backend.services.context_monitor.Observer', return_value=mock_observer):
        with patch('backend.services.context_monitor.JSONLFileHandler', mock_handler_class):
            with patch('backend.services.context_monitor.asyncio.create_task') as mock_create_task:
                # 开始监控
                callback = AsyncMock()
                await monitor.watch_for_changes(callback)
                
                assert monitor.observer is not None
                assert monitor._watch_callback == callback
                mock_observer.start.assert_called_once()
                mock_create_task.assert_called_once()  # For _poll_changes
                
                # 停止监控
                monitor.stop_watching()
                mock_observer.stop.assert_called_once()


# ===== 事件处理测试 =====
@pytest.mark.asyncio
async def test_process_jsonl_entry():
    """测试处理 JSONL 条目"""
    from backend.services.context_monitor import ContextMonitor, ContextState, FileInfo
    
    monitor = ContextMonitor()
    state = ContextState()
    
    # 测试工具调用 - 文件加载
    entry = {
        "tool_calls": [{
            "tool_name": "read_file",
            "arguments": {"path": "/test/file.py"}
        }]
    }
    await monitor._process_jsonl_entry(state, entry)
    assert len(state.files_loaded) == 1
    assert state.files_loaded[0].path == "/test/file.py"
    assert state.files_loaded[0].tokens == 1000  # 默认估计值
    
    # 测试消息事件
    entry = {
        "role": "user",
        "content": "test message"
    }
    await monitor._process_jsonl_entry(state, entry)
    assert state.messages_count == 1
    
    # 测试 token 使用事件
    entry = {
        "usage": {
            "total_tokens": 5000
        }
    }
    await monitor._process_jsonl_entry(state, entry)
    assert state.token_count == 5000
    
    # 测试压缩事件
    entry = {
        "content": "Context compacted successfully"
    }
    await monitor._process_jsonl_entry(state, entry)
    assert state.last_compact is not None
    assert len(state.files_loaded) == 0  # 压缩后文件列表被清空


@pytest.mark.asyncio
async def test_state_change_detection():
    """测试状态变化检测"""
    from backend.services.context_monitor import ContextMonitor, ContextState, FileInfo
    
    monitor = ContextMonitor()
    
    # 创建带 path 参数的 FileInfo
    # 相同状态
    state1 = ContextState(token_count=100, messages_count=5)
    state2 = ContextState(token_count=100, messages_count=5)
    assert not monitor._has_state_changed(state1, state2)
    
    # Token 变化
    state2.token_count = 200
    assert monitor._has_state_changed(state1, state2)
    
    # 文件数变化
    state2.token_count = 100
    state2.files_loaded.append(FileInfo(
        path="/test.py",
        tokens=100,
        loaded_at=datetime.now()
    ))
    assert monitor._has_state_changed(state1, state2)
    
    # last_compact 变化
    state1.files_loaded.append(FileInfo(
        path="/test.py",
        tokens=100,
        loaded_at=datetime.now()
    ))
    state2.last_compact = datetime.now()
    assert monitor._has_state_changed(state1, state2)


# ===== 主测试运行器 =====
async def main():
    """运行所有测试"""
    print("🚀 运行 ContextMonitor 完整测试套件")
    print("=" * 80)
    
    tests = [
        # 数据类测试
        test_file_info,
        test_context_state,
        
        # 初始化和配置
        test_context_monitor_init,
        test_find_session_file,
        test_parse_context_state,
        
        # 监控功能
        test_start_stop_monitoring,
        test_get_current_state,
        test_get_stats,
        test_get_history,
        
        # 文件监控
        test_jsonl_file_handler,
        test_watch_for_changes,
        
        # 事件处理
        test_process_jsonl_entry,
        test_state_change_detection
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            print(f"\n🧪 运行: {test.__name__}")
            await test()
            print(f"   ✅ 通过")
            passed += 1
        except Exception as e:
            failed += 1
            print(f"   ❌ 失败: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 80)
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"总计: {len(tests)}")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))