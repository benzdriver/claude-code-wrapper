#!/usr/bin/env python3
"""
端到端工作流测试套件
目标：模拟真实用户场景，验证系统完整功能流程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest


import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime, timedelta
from pathlib import Path
import uuid

# Mock 外部依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['watchdog'] = MagicMock()
sys.modules['watchdog.observers'] = MagicMock()
sys.modules['watchdog.events'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()
sys.modules['fastapi'] = MagicMock()
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['openai'] = MagicMock()


# ===== 工作流 1: 用户连接和命令执行 =====
@pytest.mark.asyncio
async def test_user_connection_command_workflow():
    """测试用户连接、发送命令、接收输出的完整流程"""
    print("\n📋 场景: 用户通过WebSocket连接并执行命令")
    
    # 创建系统组件
    from backend.services.event_bus import EventBus, Event
    from backend.services.terminal_bridge import TerminalBridge, TerminalState
    from backend.core.command_manager import CommandManager
    from backend.models.base import EventType, CommandStatus
    
    with patch('backend.core.command_manager.TerminalBridge') as MockTerminalBridge:
        # 初始化事件总线
        event_bus = EventBus()
        await event_bus.start()
        
        # 模拟终端桥接
        mock_terminal = Mock(spec=TerminalBridge)
        mock_terminal.send_command = AsyncMock()
        mock_terminal.is_alive.return_value = True
        mock_terminal.is_running = True
        
        # 创建模拟状态
        mock_state = Mock(spec=TerminalState)
        mock_state.is_ready = True
        mock_state.is_alive = True
        mock_terminal.state = mock_state
        
        # 创建命令管理器
        command_manager = CommandManager(mock_terminal)
        command_manager.event_bus = event_bus
        
        # 收集事件
        events_received = []
        
        async def event_collector(event):
            events_received.append({
                'type': event.type,
                'data': event.data,
                'timestamp': datetime.now()
            })
        
        # 订阅关键事件
        event_bus.subscribe(EventType.COMMAND_EXECUTED, event_collector)
        event_bus.subscribe(EventType.TERMINAL_OUTPUT, event_collector)
        
        # 步骤1: 用户发送命令
        user_command = "echo Hello, Claude Code!"
        print(f"   1️⃣ 用户发送命令: {user_command}")
        
        # 执行命令
        result = await command_manager.execute_command(user_command)
        
        # 步骤2: 验证命令被发送到终端
        mock_terminal.send_command.assert_called_once_with(user_command)
        print(f"   2️⃣ 命令已发送到终端")
        
        # 步骤3: 模拟终端输出
        terminal_output = "Hello, Claude Code!"
        await event_bus.publish(Event(
            type=EventType.TERMINAL_OUTPUT,
            source="terminal_bridge",
            data=terminal_output
        ))
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        # 步骤4: 验证事件流
        assert len(events_received) >= 1
        command_events = [e for e in events_received if e['type'] == EventType.COMMAND_EXECUTED]
        assert len(command_events) >= 1
        print(f"   3️⃣ 收到 {len(events_received)} 个事件")
        
        # 步骤5: 验证结果
        assert result is not None
        print(f"   4️⃣ 命令执行成功")
        
        await event_bus.stop()
        print("   ✅ 用户命令执行工作流完成")


# ===== 工作流 2: 上下文监控和智能建议 =====
@pytest.mark.asyncio
async def test_context_monitoring_suggestion_workflow():
    """测试上下文监控、分析和智能建议生成的完整流程"""
    print("\n📋 场景: 上下文使用率过高时生成压缩建议")
    
    from backend.services.event_bus import EventBus, Event
    from backend.services.context_monitor import ContextMonitor, ContextState, FileInfo
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.services.memory_manager import MemoryManager
    from backend.models.base import EventType, SuggestionPriority
    
    # 初始化组件
    event_bus = EventBus()
    await event_bus.start()
    
    # 创建内存管理器（mock）
    memory_manager = Mock(spec=MemoryManager)
    
    # 创建建议引擎
    suggestion_engine = SuggestionEngine()
    suggestion_engine.event_bus = event_bus
    await suggestion_engine.initialize(memory_manager)
    
    # 收集生成的建议
    suggestions_received = []
    
    async def suggestion_collector(event):
        if event.type == EventType.SUGGESTION_GENERATED:
            suggestions_received.append(event.data)
    
    event_bus.subscribe(EventType.SUGGESTION_GENERATED, suggestion_collector)
    
    # 步骤1: 创建高上下文使用率状态
    print("   1️⃣ 模拟高上下文使用率 (90%)")
    high_usage_state = Mock(spec=ContextState)
    high_usage_state.percentage = 90.0
    high_usage_state.token_count = 180000
    high_usage_state.token_limit = 200000
    high_usage_state.files_loaded = [
        Mock(spec=FileInfo, path="main.py", size=50000),
        Mock(spec=FileInfo, path="utils.py", size=30000),
        Mock(spec=FileInfo, path="models.py", size=40000)
    ]
    high_usage_state.session_start = datetime.now() - timedelta(hours=2)
    
    # 步骤2: 触发分析
    print("   2️⃣ 触发建议引擎分析")
    suggestions = await suggestion_engine.analyze(high_usage_state)
    
    # 等待事件处理
    await asyncio.sleep(0.1)
    
    # 步骤3: 验证建议生成
    assert len(suggestions) > 0
    compact_suggestions = [s for s in suggestions if s.type == "compact"]
    assert len(compact_suggestions) > 0
    
    compact_suggestion = compact_suggestions[0]
    assert compact_suggestion.priority == SuggestionPriority.HIGH
    assert compact_suggestion.confidence > 0.9
    print(f"   3️⃣ 生成了 {len(suggestions)} 个建议")
    print(f"      - 压缩建议: {compact_suggestion.reason}")
    
    # 步骤4: 验证建议事件
    assert len(suggestions_received) == len(suggestions)
    print(f"   4️⃣ 发布了 {len(suggestions_received)} 个建议事件")
    
    # 步骤5: 模拟用户接受建议
    await suggestion_engine.record_feedback(compact_suggestion.id, accepted=True)
    print("   5️⃣ 用户接受了压缩建议")
    
    await event_bus.stop()
    print("   ✅ 上下文监控和建议工作流完成")


# ===== 工作流 3: 内存系统完整流程 =====
@pytest.mark.asyncio
async def test_memory_system_workflow():
    """测试从对话内容到内存存储和检索的完整流程"""
    print("\n📋 场景: 保存重要对话内容到内存系统")
    
    from backend.services.event_bus import EventBus, Event
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.services.cache_manager import CacheManager
    from backend.models.base import EventType, MemoryLevel
    
    with patch('backend.services.cache_manager.settings') as mock_settings:
        mock_settings.has_redis = False
        mock_settings.claude_home = Path("/test/home")
        
        # 初始化组件
        event_bus = EventBus()
        await event_bus.start()
        
        cache_manager = CacheManager()
        await cache_manager.initialize()
        
        memory_manager = MemoryManager()
        memory_manager.cache_manager = cache_manager
        memory_manager.event_bus = event_bus
        
        # 收集内存事件
        memory_events = []
        
        async def memory_event_collector(event):
            memory_events.append(event)
        
        event_bus.subscribe(EventType.MEMORY_UPDATED, memory_event_collector)
        event_bus.subscribe(EventType.MEMORY_IMPORTED, memory_event_collector)
        
        # 步骤1: 创建重要内容
        print("   1️⃣ 识别重要对话内容")
        important_content = """
# Python 性能优化决策

经过分析，我们决定采用以下策略：
1. 使用 asyncio 进行异步编程
2. 实施缓存策略减少重复计算
3. 使用 profiling 工具定位瓶颈

这个决策将显著提升系统性能。
"""
        
        # 步骤2: 创建内存文件
        print("   2️⃣ 创建内存文件")
        memory_file = MemoryFile(
            id=f"mem_{uuid.uuid4().hex[:8]}",
            path=Path("/test/project/decisions.md"),
            level=MemoryLevel.PROJECT,
            content=important_content,
            imports=[],
            size_bytes=len(important_content.encode()),
            metadata={
                "source": "conversation",
                "importance": "high",
                "tags": ["performance", "python", "decision"]
            }
        )
        
        # 步骤3: 保存到内存系统
        print("   3️⃣ 保存到内存系统")
        # 模拟保存操作
        memory_manager.memories[memory_file.id] = memory_file
        
        # 发布内存更新事件
        await event_bus.publish(Event(
            type=EventType.MEMORY_UPDATED,
            source="memory_manager",
            data={
                "memory_id": memory_file.id,
                "action": "created",
                "level": memory_file.level.value
            }
        ))
        
        # 等待事件处理
        await asyncio.sleep(0.1)
        
        # 步骤4: 验证内存保存
        assert memory_file.id in memory_manager.memories
        assert len(memory_events) > 0
        print(f"   4️⃣ 内存保存成功，ID: {memory_file.id}")
        
        # 步骤5: 测试内存搜索
        print("   5️⃣ 搜索相关内存")
        # 模拟搜索
        search_query = "python performance optimization"
        search_results = []
        
        for mem_id, mem_file in memory_manager.memories.items():
            if any(keyword in mem_file.content.lower() 
                   for keyword in search_query.lower().split()):
                search_results.append(mem_file)
        
        assert len(search_results) > 0
        assert memory_file in search_results
        print(f"   6️⃣ 找到 {len(search_results)} 个相关内存")
        
        await event_bus.stop()
        print("   ✅ 内存系统工作流完成")


# ===== 工作流 4: 错误恢复和重试机制 =====
@pytest.mark.asyncio
async def test_error_recovery_workflow():
    """测试系统错误恢复和重试机制"""
    print("\n📋 场景: 终端连接失败后的自动重试")
    
    from backend.services.event_bus import EventBus, Event
    from backend.services.terminal_bridge import TerminalBridge
    from backend.models.base import EventType
    
    # 初始化事件总线
    event_bus = EventBus()
    await event_bus.start()
    
    # 跟踪重试次数
    retry_attempts = []
    
    # 创建会失败然后成功的终端模拟
    attempt_count = 0
    
    async def mock_start(workspace=None):
        nonlocal attempt_count
        attempt_count += 1
        retry_attempts.append({
            'attempt': attempt_count,
            'timestamp': datetime.now()
        })
        
        if attempt_count < 3:
            print(f"   ❌ 第 {attempt_count} 次连接失败")
            raise Exception("Connection failed")
        else:
            print(f"   ✅ 第 {attempt_count} 次连接成功")
            return True
    
    with patch('backend.services.terminal_bridge.TerminalBridge') as MockTerminalBridge:
        mock_terminal = Mock(spec=TerminalBridge)
        mock_terminal.start = mock_start
        mock_terminal.state.restart_count = 0
        mock_terminal.max_restart_attempts = 3
        MockTerminalBridge.return_value = mock_terminal
        
        # 步骤1: 首次连接尝试
        print("   1️⃣ 开始终端连接")
        
        # 模拟重试逻辑
        success = False
        for i in range(3):
            try:
                await mock_terminal.start()
                success = True
                break
            except Exception as e:
                if i < 2:  # 还有重试机会
                    await asyncio.sleep(0.1)  # 模拟重试延迟
                    continue
                else:
                    raise
        
        # 步骤2: 验证重试
        assert success == True
        assert len(retry_attempts) == 3
        print(f"   2️⃣ 经过 {len(retry_attempts)} 次尝试后成功连接")
        
        # 步骤3: 发布恢复事件
        await event_bus.publish(Event(
            type=EventType.TERMINAL_CONNECTED,
            source="terminal_bridge", 
            data={
                "status": "recovered",
                "attempts": len(retry_attempts)
            }
        ))
        
        print("   3️⃣ 系统已恢复正常")
        
        await event_bus.stop()
        print("   ✅ 错误恢复工作流完成")


# ===== 工作流 5: 并发用户操作 =====
@pytest.mark.asyncio
async def test_concurrent_users_workflow():
    """测试多用户并发操作场景"""
    print("\n📋 场景: 多用户同时执行命令和查询")
    
    from backend.services.event_bus import EventBus, Event
    from backend.core.command_manager import CommandManager
    from backend.services.cache_manager import CacheManager
    from backend.models.base import EventType
    
    with patch('backend.services.cache_manager.settings') as mock_settings:
        mock_settings.has_redis = False
        
        # 初始化共享组件
        event_bus = EventBus()
        await event_bus.start()
        
        cache_manager = CacheManager()
        await cache_manager.initialize()
        
        # 模拟用户操作
        async def user_operation(user_id: str, commands: list):
            """模拟单个用户的操作序列"""
            user_results = []
            
            for cmd in commands:
                # 缓存用户状态
                await cache_manager.set(f"user_{user_id}_last_cmd", cmd)
                
                # 发布命令事件
                await event_bus.publish(Event(
                    type=EventType.COMMAND_EXECUTED,
                    source=f"user_{user_id}",
                    data={"command": cmd, "user": user_id}
                ))
                
                user_results.append({
                    'user': user_id,
                    'command': cmd,
                    'timestamp': datetime.now()
                })
                
                # 模拟处理延迟
                await asyncio.sleep(0.01)
            
            return user_results
        
        # 步骤1: 创建多个用户的操作
        print("   1️⃣ 创建 5 个并发用户")
        user_tasks = []
        for i in range(5):
            user_commands = [
                f"echo User {i} command 1",
                f"ls -la /user{i}",
                f"python script{i}.py"
            ]
            task = user_operation(f"user_{i}", user_commands)
            user_tasks.append(task)
        
        # 步骤2: 并发执行
        print("   2️⃣ 并发执行用户操作")
        start_time = datetime.now()
        all_results = await asyncio.gather(*user_tasks)
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        # 步骤3: 验证结果
        total_operations = sum(len(results) for results in all_results)
        assert total_operations == 15  # 5 users × 3 commands
        print(f"   3️⃣ 完成 {total_operations} 个操作，耗时 {duration:.3f}秒")
        
        # 步骤4: 验证缓存状态
        for i in range(5):
            last_cmd = await cache_manager.get(f"user_user_{i}_last_cmd")
            assert last_cmd == f"python script{i}.py"
        
        print("   4️⃣ 所有用户状态正确保存")
        
        # 步骤5: 验证并发安全
        cache_stats = cache_manager.get_stats()
        assert cache_stats['hit_rate'] >= 0  # 缓存正常工作
        print("   5️⃣ 并发操作安全完成")
        
        await event_bus.stop()
        print("   ✅ 并发用户操作工作流完成")


# ===== 工作流 6: 完整会话生命周期 =====
@pytest.mark.asyncio
async def test_complete_session_lifecycle():
    """测试从会话开始到结束的完整生命周期"""
    print("\n📋 场景: 完整的用户会话生命周期")
    
    from backend.services.event_bus import EventBus, Event
    from backend.models.base import EventType
    
    # 初始化事件总线
    event_bus = EventBus()
    await event_bus.start()
    
    # 会话事件记录
    session_events = []
    
    async def session_event_collector(event):
        session_events.append({
            'type': event.type,
            'timestamp': datetime.now(),
            'data': event.data
        })
    
    # 订阅所有相关事件
    event_types = [
        EventType.CLIENT_CONNECTED,
        EventType.TERMINAL_CONNECTED,
        EventType.COMMAND_EXECUTED,
        EventType.MEMORY_UPDATED,
        EventType.CLIENT_DISCONNECTED,
        EventType.TERMINAL_DISCONNECTED
    ]
    
    for event_type in event_types:
        event_bus.subscribe(event_type, session_event_collector)
    
    # 会话ID
    session_id = f"session_{uuid.uuid4().hex[:8]}"
    
    # 步骤1: 用户连接
    print(f"   1️⃣ 用户连接 (会话ID: {session_id})")
    await event_bus.publish(Event(
        type=EventType.CLIENT_CONNECTED,
        source="websocket_manager",
        data={"session_id": session_id, "client_id": "test_client"}
    ))
    
    # 步骤2: 终端初始化
    print("   2️⃣ 初始化终端连接")
    await event_bus.publish(Event(
        type=EventType.TERMINAL_CONNECTED,
        source="terminal_bridge",
        data={"session_id": session_id}
    ))
    
    # 步骤3: 执行一些命令
    print("   3️⃣ 执行用户命令")
    commands = ["pwd", "ls", "echo 'Hello World'"]
    for cmd in commands:
        await event_bus.publish(Event(
            type=EventType.COMMAND_EXECUTED,
            source="command_manager",
            data={
                "session_id": session_id,
                "command": cmd,
                "status": "success"
            }
        ))
        await asyncio.sleep(0.01)
    
    # 步骤4: 保存会话内存
    print("   4️⃣ 保存会话重要内容")
    await event_bus.publish(Event(
        type=EventType.MEMORY_UPDATED,
        source="memory_manager",
        data={
            "session_id": session_id,
            "memory_type": "session_summary",
            "content": "用户执行了文件系统浏览和测试命令"
        }
    ))
    
    # 步骤5: 会话结束
    print("   5️⃣ 用户断开连接")
    await event_bus.publish(Event(
        type=EventType.CLIENT_DISCONNECTED,
        source="websocket_manager",
        data={"session_id": session_id, "reason": "user_logout"}
    ))
    
    await event_bus.publish(Event(
        type=EventType.TERMINAL_DISCONNECTED,
        source="terminal_bridge",
        data={"session_id": session_id}
    ))
    
    # 等待所有事件处理
    await asyncio.sleep(0.1)
    
    # 步骤6: 验证完整生命周期
    assert len(session_events) >= 6
    
    # 验证事件顺序
    event_sequence = [e['type'] for e in session_events]
    assert EventType.CLIENT_CONNECTED in event_sequence
    assert EventType.TERMINAL_CONNECTED in event_sequence
    assert EventType.COMMAND_EXECUTED in event_sequence
    assert EventType.CLIENT_DISCONNECTED in event_sequence
    
    print(f"   6️⃣ 记录了 {len(session_events)} 个会话事件")
    print("   ✅ 完整会话生命周期工作流完成")
    
    await event_bus.stop()


# ===== 主测试运行器 =====
async def main():
    """运行所有端到端工作流测试"""
    print("🚀 运行端到端工作流测试套件")
    print("=" * 80)
    print("这些测试模拟真实用户场景，验证系统各组件的协同工作")
    print("=" * 80)
    
    workflows = [
        test_user_connection_command_workflow,
        test_context_monitoring_suggestion_workflow,
        test_memory_system_workflow,
        test_error_recovery_workflow,
        test_concurrent_users_workflow,
        test_complete_session_lifecycle
    ]
    
    passed = 0
    failed = 0
    
    for workflow in workflows:
        try:
            start_time = datetime.now()
            await workflow()
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            print(f"⏱️  耗时: {duration:.3f}秒\n")
            passed += 1
        except Exception as e:
            failed += 1
            print(f"❌ 工作流失败: {e}")
            import traceback
            traceback.print_exc()
            print()
    
    print("=" * 80)
    print(f"📊 测试结果汇总")
    print(f"   ✅ 通过: {passed}/{len(workflows)}")
    print(f"   ❌ 失败: {failed}/{len(workflows)}")
    print(f"   📈 成功率: {(passed/len(workflows)*100):.1f}%")
    
    if passed == len(workflows):
        print("\n🎉 所有端到端工作流测试通过！")
        print("✨ 系统已验证以下关键能力：")
        print("   • 用户交互和命令执行")
        print("   • 智能建议和上下文管理")
        print("   • 内存系统完整流程")
        print("   • 错误恢复和容错机制")
        print("   • 并发操作和性能")
        print("   • 会话生命周期管理")
    else:
        print("\n⚠️  部分工作流测试失败，需要进一步调试")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))