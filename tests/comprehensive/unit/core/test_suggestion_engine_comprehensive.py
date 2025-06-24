#!/usr/bin/env python3
"""
SuggestionEngine 完整测试套件
目标：提升 SuggestionEngine 覆盖率到 70%+
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest


import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
from pathlib import Path

# Mock 外部依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['watchdog'] = MagicMock()
sys.modules['watchdog.observers'] = MagicMock()
sys.modules['watchdog.events'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()


# ===== Suggestion 数据类测试 =====
@pytest.mark.asyncio
async def test_suggestion_creation():
    """测试 Suggestion 数据类创建"""
    from backend.core.suggestion_engine import Suggestion
    from backend.models.base import SuggestionPriority
    
    # 基本创建
    suggestion = Suggestion(
        id="test_1",
        type="compact",
        command="/compact",
        reason="Test reason",
        priority=SuggestionPriority.HIGH,
        confidence=0.9
    )
    
    assert suggestion.id == "test_1"
    assert suggestion.type == "compact"
    assert suggestion.command == "/compact"
    assert suggestion.reason == "Test reason"
    assert suggestion.priority == SuggestionPriority.HIGH
    assert suggestion.confidence == 0.9
    assert suggestion.auto_execute == False
    assert isinstance(suggestion.metadata, dict)
    assert isinstance(suggestion.created_at, datetime)


@pytest.mark.asyncio
async def test_suggestion_with_metadata():
    """测试带有元数据的 Suggestion"""
    from backend.core.suggestion_engine import Suggestion
    from backend.models.base import SuggestionPriority
    
    metadata = {"key": "value", "count": 10}
    suggestion = Suggestion(
        id="test_2",
        type="clear",
        command="/clear",
        reason="Test with metadata",
        priority=SuggestionPriority.MEDIUM,
        confidence=0.7,
        auto_execute=True,
        metadata=metadata
    )
    
    assert suggestion.auto_execute == True
    assert suggestion.metadata == metadata
    assert suggestion.metadata["count"] == 10


# ===== HighContextUsageRule 测试 =====
@pytest.mark.asyncio
async def test_high_context_usage_rule_trigger():
    """测试高上下文使用率规则触发"""
    from backend.core.suggestion_engine import HighContextUsageRule
    from backend.services.context_monitor import ContextState
    
    rule = HighContextUsageRule()
    
    # 创建模拟上下文状态 - 高使用率
    context_state = Mock(spec=ContextState)
    context_state.percentage = 85.0
    context_state.token_count = 85000
    
    context = {'context_state': context_state}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is not None
    assert suggestion.type == "compact"
    assert suggestion.command == "/compact"
    assert "85.0%" in suggestion.reason
    assert suggestion.confidence == 0.95
    assert suggestion.metadata['current_usage'] == 85.0
    assert suggestion.metadata['threshold'] == 80.0


@pytest.mark.asyncio
async def test_high_context_usage_rule_no_trigger():
    """测试高上下文使用率规则不触发"""
    from backend.core.suggestion_engine import HighContextUsageRule
    from backend.services.context_monitor import ContextState
    
    rule = HighContextUsageRule()
    
    # 创建模拟上下文状态 - 低使用率
    context_state = Mock(spec=ContextState)
    context_state.percentage = 50.0
    
    context = {'context_state': context_state}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


@pytest.mark.asyncio
async def test_high_context_usage_rule_no_state():
    """测试高上下文使用率规则无状态"""
    from backend.core.suggestion_engine import HighContextUsageRule
    
    rule = HighContextUsageRule()
    
    context = {}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


# ===== TaskSwitchRule 测试 =====
@pytest.mark.asyncio
async def test_task_switch_rule_trigger():
    """测试任务切换规则触发"""
    from backend.core.suggestion_engine import TaskSwitchRule
    from backend.services.context_monitor import ContextState, FileInfo
    
    rule = TaskSwitchRule()
    
    # 创建文件信息
    old_files = [
        Mock(spec=FileInfo, path="file1.py"),
        Mock(spec=FileInfo, path="file2.py"),
        Mock(spec=FileInfo, path="file3.py")
    ]
    
    new_files = [
        Mock(spec=FileInfo, path="file4.py"),  # 完全不同的文件
        Mock(spec=FileInfo, path="file5.py"),
        Mock(spec=FileInfo, path="file6.py")
    ]
    
    # 当前状态和之前状态
    current_state = Mock(spec=ContextState)
    current_state.files_loaded = new_files
    
    previous_state = Mock(spec=ContextState)
    previous_state.files_loaded = old_files
    
    context = {
        'context_state': current_state,
        'previous_state': previous_state
    }
    
    suggestion = await rule.evaluate(context)
    
    assert suggestion is not None
    assert suggestion.type == "clear"
    assert suggestion.command == "/clear"
    assert "task switch" in suggestion.reason.lower()
    assert suggestion.metadata['change_ratio'] > 0.7


@pytest.mark.asyncio
async def test_task_switch_rule_no_change():
    """测试任务切换规则无变化"""
    from backend.core.suggestion_engine import TaskSwitchRule
    from backend.services.context_monitor import ContextState, FileInfo
    
    rule = TaskSwitchRule()
    
    # 相同的文件
    files = [
        Mock(spec=FileInfo, path="file1.py"),
        Mock(spec=FileInfo, path="file2.py")
    ]
    
    current_state = Mock(spec=ContextState)
    current_state.files_loaded = files
    
    previous_state = Mock(spec=ContextState)
    previous_state.files_loaded = files
    
    context = {
        'context_state': current_state,
        'previous_state': previous_state
    }
    
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


@pytest.mark.asyncio
async def test_task_switch_rule_no_previous():
    """测试任务切换规则无之前状态"""
    from backend.core.suggestion_engine import TaskSwitchRule
    from backend.services.context_monitor import ContextState, FileInfo
    
    rule = TaskSwitchRule()
    
    current_state = Mock(spec=ContextState)
    current_state.files_loaded = [Mock(spec=FileInfo, path="file1.py")]
    
    context = {'context_state': current_state}
    
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


# ===== RepeatedFileAccessRule 测试 =====
@pytest.mark.asyncio
async def test_repeated_file_access_rule_trigger():
    """测试重复文件访问规则触发"""
    from backend.core.suggestion_engine import RepeatedFileAccessRule
    
    rule = RepeatedFileAccessRule()
    
    file_access_count = {
        "main.py": 8,  # 高频访问
        "utils.py": 3,
        "config.py": 2
    }
    
    context = {'file_access_count': file_access_count}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is not None
    assert suggestion.type == "add_to_memory"
    assert "main.py" in suggestion.command
    assert "8 times" in suggestion.reason
    assert suggestion.metadata['file'] == "main.py"
    assert suggestion.metadata['access_count'] == 8


@pytest.mark.asyncio
async def test_repeated_file_access_rule_no_frequent():
    """测试重复文件访问规则无高频文件"""
    from backend.core.suggestion_engine import RepeatedFileAccessRule
    
    rule = RepeatedFileAccessRule()
    
    file_access_count = {
        "main.py": 2,  # 低频访问
        "utils.py": 1
    }
    
    context = {'file_access_count': file_access_count}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


@pytest.mark.asyncio
async def test_repeated_file_access_rule_empty():
    """测试重复文件访问规则空数据"""
    from backend.core.suggestion_engine import RepeatedFileAccessRule
    
    rule = RepeatedFileAccessRule()
    
    context = {'file_access_count': {}}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


# ===== LongSessionRule 测试 =====
@pytest.mark.asyncio
async def test_long_session_rule_trigger():
    """测试长会话规则触发"""
    from backend.core.suggestion_engine import LongSessionRule
    from backend.services.context_monitor import ContextState
    
    rule = LongSessionRule()
    
    # 创建3小时前开始的会话
    session_start = datetime.now() - timedelta(hours=3)
    context_state = Mock(spec=ContextState)
    context_state.session_start = session_start
    
    context = {'context_state': context_state}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is not None
    assert suggestion.type == "save_progress"
    assert "3.0 hours" in suggestion.reason
    assert suggestion.metadata['session_duration_hours'] > 2.5


@pytest.mark.asyncio
async def test_long_session_rule_short_session():
    """测试长会话规则短会话"""
    from backend.core.suggestion_engine import LongSessionRule
    from backend.services.context_monitor import ContextState
    
    rule = LongSessionRule()
    
    # 创建30分钟前开始的会话
    session_start = datetime.now() - timedelta(minutes=30)
    context_state = Mock(spec=ContextState)
    context_state.session_start = session_start
    
    context = {'context_state': context_state}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


# ===== ImportantDecisionRule 测试 =====
@pytest.mark.asyncio
async def test_important_decision_rule_trigger():
    """测试重要决策规则触发"""
    from backend.core.suggestion_engine import ImportantDecisionRule
    
    rule = ImportantDecisionRule()
    
    recent_output = """
    After reviewing the code, I decided to use the factory pattern.
    This approach will provide better flexibility and maintainability.
    The strategy should focus on scalability.
    """
    
    context = {'recent_output': recent_output}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is not None
    assert suggestion.type == "save_decision"
    assert "decided" in suggestion.reason.lower()
    assert "decision" in suggestion.reason.lower()
    assert len(suggestion.metadata['keywords_found']) > 0
    assert "decided" in suggestion.metadata['keywords_found']


@pytest.mark.asyncio
async def test_important_decision_rule_no_keywords():
    """测试重要决策规则无关键词"""
    from backend.core.suggestion_engine import ImportantDecisionRule
    
    rule = ImportantDecisionRule()
    
    recent_output = "Just regular output without important keywords."
    
    context = {'recent_output': recent_output}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


@pytest.mark.asyncio
async def test_important_decision_rule_empty_output():
    """测试重要决策规则空输出"""
    from backend.core.suggestion_engine import ImportantDecisionRule
    
    rule = ImportantDecisionRule()
    
    context = {'recent_output': ''}
    suggestion = await rule.evaluate(context)
    
    assert suggestion is None


# ===== SuggestionEngine 初始化测试 =====
@pytest.mark.asyncio
async def test_suggestion_engine_init():
    """测试 SuggestionEngine 初始化"""
    from backend.core.suggestion_engine import SuggestionEngine
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        assert engine.event_bus == mock_bus
        assert engine.memory_manager is None
        assert len(engine.rules) == 5  # 内置规则数量
        assert len(engine.suggestion_history) == 0
        assert len(engine.feedback_history) == 0
        assert len(engine.file_access_count) == 0
        assert len(engine.recent_outputs) == 0
        assert engine.previous_state is None


@pytest.mark.asyncio
async def test_suggestion_engine_initialize():
    """测试 SuggestionEngine initialize 方法"""
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.models.base import EventType
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        mock_memory_manager = Mock()
        
        await engine.initialize(mock_memory_manager)
        
        assert engine.memory_manager == mock_memory_manager
        
        # 验证订阅了事件
        assert mock_bus.subscribe.call_count == 2
        mock_bus.subscribe.assert_any_call(EventType.TERMINAL_OUTPUT, engine._on_terminal_output)
        mock_bus.subscribe.assert_any_call(EventType.CONTEXT_UPDATED, engine._on_context_updated)


# ===== SuggestionEngine analyze 测试 =====
@pytest.mark.asyncio
async def test_suggestion_engine_analyze():
    """测试 SuggestionEngine analyze 方法"""
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.services.context_monitor import ContextState
    from backend.models.base import EventType
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_bus.publish = AsyncMock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        # 创建高上下文使用率状态
        context_state = Mock(spec=ContextState)
        context_state.percentage = 90.0
        context_state.token_count = 90000
        
        suggestions = await engine.analyze(context_state)
        
        # 应该触发高上下文使用率建议
        assert len(suggestions) > 0
        assert any(s.type == "compact" for s in suggestions)
        
        # 验证发布了事件
        assert mock_bus.publish.call_count == len(suggestions)


@pytest.mark.asyncio
async def test_suggestion_engine_get_suggestions_limit_warning():
    """测试基于事件的建议生成 - 上下文限制警告"""
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.services.event_bus import Event
    from backend.models.base import EventType, SuggestionPriority
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        event = Event(
            type=EventType.CONTEXT_LIMIT_WARNING,
            source="test",
            data={}
        )
        
        suggestions = await engine.get_suggestions(event)
        
        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion.type == "compact"
        assert suggestion.command == "/compact"
        assert suggestion.priority == SuggestionPriority.HIGH
        assert suggestion.confidence == 1.0


@pytest.mark.asyncio
async def test_suggestion_engine_get_suggestions_command_failed():
    """测试基于事件的建议生成 - 命令失败"""
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.services.event_bus import Event
    from backend.models.base import EventType
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        event = Event(
            type=EventType.COMMAND_FAILED,
            source="test",
            data={'error': 'command not found'}
        )
        
        suggestions = await engine.get_suggestions(event)
        
        assert len(suggestions) == 1
        suggestion = suggestions[0]
        assert suggestion.type == "help"
        assert suggestion.command == "/help"


# ===== SuggestionEngine 其他方法测试 =====
@pytest.mark.asyncio
async def test_suggestion_engine_register_rule():
    """测试注册自定义规则"""
    from backend.core.suggestion_engine import SuggestionEngine, SuggestionRule
    from backend.models.base import SuggestionPriority
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        initial_rules = len(engine.rules)
        
        # 创建自定义规则
        custom_rule = SuggestionRule(
            name="custom_rule",
            description="Test rule",
            priority=SuggestionPriority.LOW
        )
        
        engine.register_rule(custom_rule)
        
        assert len(engine.rules) == initial_rules + 1
        assert custom_rule in engine.rules


@pytest.mark.asyncio
async def test_suggestion_engine_record_feedback():
    """测试记录用户反馈"""
    from backend.core.suggestion_engine import SuggestionEngine, Suggestion
    from backend.models.base import SuggestionPriority, EventType
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_bus.publish = AsyncMock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        # 添加建议到历史
        suggestion = Suggestion(
            id="test_suggestion",
            type="compact",
            command="/compact",
            reason="Test",
            priority=SuggestionPriority.HIGH,
            confidence=0.9
        )
        engine.suggestion_history.append(suggestion)
        
        # 记录正面反馈
        await engine.record_feedback("test_suggestion", True)
        
        assert engine.feedback_history["test_suggestion"] == True
        
        # 验证发布了反馈事件
        mock_bus.publish.assert_called_once()
        call_args = mock_bus.publish.call_args[0][0]
        assert call_args.type == EventType.SUGGESTION_ACCEPTED


@pytest.mark.asyncio
async def test_suggestion_engine_get_stats():
    """测试获取统计信息"""
    from backend.core.suggestion_engine import SuggestionEngine, Suggestion
    from backend.models.base import SuggestionPriority
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        # 添加一些历史数据
        suggestion = Suggestion(
            id="test_1",
            type="compact",
            command="/compact",
            reason="Test",
            priority=SuggestionPriority.HIGH,
            confidence=0.9
        )
        engine.suggestion_history.append(suggestion)
        engine.feedback_history["test_1"] = True
        engine.file_access_count["file1.py"] = 5
        
        stats = engine.get_stats()
        
        assert stats['total_suggestions'] == 1
        assert stats['total_feedback'] == 1
        assert stats['acceptance_rate'] == 1.0
        assert stats['active_rules'] == 5  # 所有内置规则都启用
        assert stats['file_access_tracking'] == 1
        assert len(stats['rule_stats']) == 5


# ===== 事件处理测试 =====
@pytest.mark.asyncio
async def test_on_terminal_output():
    """测试终端输出事件处理"""
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.services.event_bus import Event
    from backend.models.base import EventType
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        event = Event(
            type=EventType.TERMINAL_OUTPUT,
            source="terminal",
            data="Test output line"
        )
        
        await engine._on_terminal_output(event)
        
        assert len(engine.recent_outputs) == 1
        assert engine.recent_outputs[0] == "Test output line"


@pytest.mark.asyncio
async def test_on_context_updated():
    """测试上下文更新事件处理"""
    from backend.core.suggestion_engine import SuggestionEngine
    from backend.services.event_bus import Event
    from backend.models.base import EventType
    from backend.services.context_monitor import ContextState, FileInfo
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = SuggestionEngine()
        
        # 创建模拟状态
        file_info = Mock(spec=FileInfo)
        file_info.path = "test.py"
        
        context_state = Mock(spec=ContextState)
        context_state.files_loaded = [file_info]
        
        event = Event(
            type=EventType.CONTEXT_UPDATED,
            source="context_monitor",
            data={'context_state': context_state}
        )
        
        await engine._on_context_updated(event)
        
        # 验证文件访问计数更新
        assert engine.file_access_count["test.py"] == 1


# ===== 工厂函数测试 =====
@pytest.mark.asyncio
async def test_create_suggestion_engine():
    """测试工厂函数"""
    from backend.core.suggestion_engine import create_suggestion_engine
    
    with patch('backend.core.suggestion_engine.get_event_bus') as mock_event_bus:
        mock_bus = Mock()
        mock_event_bus.return_value = mock_bus
        
        engine = create_suggestion_engine()
        
        assert engine is not None
        assert len(engine.rules) == 5


# ===== 主测试运行器 =====
async def main():
    """运行所有测试"""
    print("🚀 运行 SuggestionEngine 完整测试套件")
    print("=" * 80)
    
    tests = [
        # 数据类测试
        test_suggestion_creation,
        test_suggestion_with_metadata,
        
        # HighContextUsageRule 测试
        test_high_context_usage_rule_trigger,
        test_high_context_usage_rule_no_trigger,
        test_high_context_usage_rule_no_state,
        
        # TaskSwitchRule 测试
        test_task_switch_rule_trigger,
        test_task_switch_rule_no_change,
        test_task_switch_rule_no_previous,
        
        # RepeatedFileAccessRule 测试
        test_repeated_file_access_rule_trigger,
        test_repeated_file_access_rule_no_frequent,
        test_repeated_file_access_rule_empty,
        
        # LongSessionRule 测试
        test_long_session_rule_trigger,
        test_long_session_rule_short_session,
        
        # ImportantDecisionRule 测试
        test_important_decision_rule_trigger,
        test_important_decision_rule_no_keywords,
        test_important_decision_rule_empty_output,
        
        # SuggestionEngine 测试
        test_suggestion_engine_init,
        test_suggestion_engine_initialize,
        test_suggestion_engine_analyze,
        test_suggestion_engine_get_suggestions_limit_warning,
        test_suggestion_engine_get_suggestions_command_failed,
        test_suggestion_engine_register_rule,
        test_suggestion_engine_record_feedback,
        test_suggestion_engine_get_stats,
        
        # 事件处理测试
        test_on_terminal_output,
        test_on_context_updated,
        
        # 工厂函数测试
        test_create_suggestion_engine
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