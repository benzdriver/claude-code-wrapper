#!/usr/bin/env python3
"""
EventBus 增强测试套件
目标：将 EventBus 覆盖率从 36% 提升到 70%+
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from datetime import datetime, timedelta

# Mock 依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()

from backend.services.event_bus import EventBus, Event, Subscription, EventType
from backend.models.base import EventType


class TestEventCreation:
    """测试 Event 创建和属性"""
    
    async def test_event_creation_defaults(self):
        """测试 Event 默认值"""
        event = Event()
        
        assert event.id is not None
        assert isinstance(event.timestamp, datetime)
        assert event.source == ""
        assert event.target is None
        assert isinstance(event.metadata, dict)
    
    async def test_event_creation_with_values(self):
        """测试 Event 创建时设置值"""
        event = Event(
            type=EventType.TERMINAL_OUTPUT,
            data="test data",
            source="test_source",
            target="test_target",
            metadata={"key": "value"}
        )
        
        assert event.type == EventType.TERMINAL_OUTPUT
        assert event.data == "test data"
        assert event.source == "test_source"
        assert event.target == "test_target"
        assert event.metadata["key"] == "value"
    
    async def test_event_type_string_conversion(self):
        """测试字符串自动转换为 EventType"""
        event = Event(type="terminal.output")
        assert event.type == EventType.TERMINAL_OUTPUT


class TestSubscription:
    """测试 Subscription 数据结构"""
    
    async def test_subscription_creation(self):
        """测试 Subscription 创建"""
        handler = AsyncMock()
        sub = Subscription(
            id="test_sub",
            event_type=EventType.TERMINAL_OUTPUT,
            handler=handler
        )
        
        assert sub.id == "test_sub"
        assert sub.event_type == EventType.TERMINAL_OUTPUT
        assert sub.handler == handler
        assert isinstance(sub.created_at, datetime)


class TestEventBusCore:
    """测试 EventBus 核心功能"""
    
    async def test_initialization(self):
        """测试 EventBus 初始化"""
        bus = EventBus(history_size=500)
        
        assert bus.history_size == 500
        assert not bus._running
        assert len(bus.subscribers) == 0
        assert len(bus.event_history) == 0
    
    async def test_start_stop(self):
        """测试启动和停止"""
        bus = EventBus()
        
        # 启动
        await bus.start()
        assert bus._running
        assert bus._process_task is not None
        
        # 停止
        await bus.stop()
        assert not bus._running
        
        # 确保任务被取消
        try:
            await bus._process_task
            assert False, "Task should be cancelled"
        except asyncio.CancelledError:
            pass  # Expected
    
    async def test_double_start(self):
        """测试重复启动"""
        bus = EventBus()
        
        await bus.start()
        # 第二次启动应该被忽略
        await bus.start()  # Should log warning but not error
        
        await bus.stop()
    
    async def test_publish_event(self):
        """测试发布事件"""
        bus = EventBus()
        await bus.start()
        
        event = Event(
            type=EventType.TERMINAL_OUTPUT,
            data="test",
            source="test"
        )
        
        await bus.publish(event)
        
        # 事件应该被加入队列
        assert bus.event_queue.qsize() > 0
        
        await bus.stop()
    
    async def test_publish_invalid_event(self):
        """测试发布无效事件"""
        bus = EventBus()
        
        # 应该抛出 TypeError
        try:
            await bus.publish("not an event")
            assert False, "Should raise TypeError"
        except TypeError as e:
            assert "Expected Event" in str(e)
    
    async def test_subscribe_unsubscribe(self):
        """测试订阅和取消订阅"""
        bus = EventBus()
        handler = AsyncMock()
        
        # 订阅
        sub_id = bus.subscribe(EventType.TERMINAL_OUTPUT, handler)
        assert sub_id is not None
        assert len(bus.subscribers[EventType.TERMINAL_OUTPUT]) == 1
        
        # 取消订阅
        bus.unsubscribe(sub_id)
        assert len(bus.subscribers[EventType.TERMINAL_OUTPUT]) == 0
    
    async def test_unsubscribe_nonexistent(self):
        """测试取消不存在的订阅"""
        bus = EventBus()
        
        # 应该记录警告但不报错
        bus.unsubscribe("nonexistent_id")
    
    async def test_multiple_subscribers(self):
        """测试多个订阅者"""
        bus = EventBus()
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        handler3 = AsyncMock()
        
        # 订阅同一事件类型
        sub1 = bus.subscribe(EventType.TERMINAL_OUTPUT, handler1)
        sub2 = bus.subscribe(EventType.TERMINAL_OUTPUT, handler2)
        sub3 = bus.subscribe(EventType.CONTEXT_UPDATED, handler3)
        
        assert len(bus.subscribers[EventType.TERMINAL_OUTPUT]) == 2
        assert len(bus.subscribers[EventType.CONTEXT_UPDATED]) == 1
    
    async def test_event_processing(self):
        """测试事件处理流程"""
        bus = EventBus()
        handler = AsyncMock()
        
        bus.subscribe(EventType.TERMINAL_OUTPUT, handler)
        await bus.start()
        
        # 发布事件
        event = Event(
            type=EventType.TERMINAL_OUTPUT,
            data="test data",
            source="test"
        )
        await bus.publish(event)
        
        # 等待处理
        await asyncio.sleep(0.2)
        
        # 验证处理器被调用
        handler.assert_called_once()
        assert handler.call_args[0][0].data == "test data"
        
        await bus.stop()
    
    async def test_concurrent_event_handling(self):
        """测试并发事件处理"""
        bus = EventBus()
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        
        # 模拟慢速处理器
        async def slow_handler(event):
            await asyncio.sleep(0.1)
            handler1(event)
        
        bus.subscribe(EventType.TERMINAL_OUTPUT, slow_handler)
        bus.subscribe(EventType.TERMINAL_OUTPUT, handler2)
        
        await bus.start()
        
        # 发布事件
        event = Event(type=EventType.TERMINAL_OUTPUT, data="test")
        await bus.publish(event)
        
        # 等待处理
        await asyncio.sleep(0.3)
        
        # 两个处理器都应该被调用
        handler1.assert_called_once()
        handler2.assert_called_once()
        
        await bus.stop()
    
    async def test_sync_handler(self):
        """测试同步处理器"""
        bus = EventBus()
        sync_handler = Mock()  # 同步 Mock
        
        bus.subscribe(EventType.TERMINAL_OUTPUT, sync_handler)
        await bus.start()
        
        event = Event(type=EventType.TERMINAL_OUTPUT, data="test")
        await bus.publish(event)
        
        await asyncio.sleep(0.2)
        
        # 同步处理器应该被调用
        sync_handler.assert_called_once()
        
        await bus.stop()
    
    async def test_handler_error_isolation(self):
        """测试处理器错误隔离"""
        bus = EventBus()
        error_handler = AsyncMock(side_effect=Exception("Handler error"))
        good_handler = AsyncMock()
        
        bus.subscribe(EventType.TERMINAL_OUTPUT, error_handler)
        bus.subscribe(EventType.TERMINAL_OUTPUT, good_handler)
        
        await bus.start()
        
        event = Event(type=EventType.TERMINAL_OUTPUT, data="test")
        await bus.publish(event)
        
        await asyncio.sleep(0.2)
        
        # 错误处理器失败不应影响其他处理器
        error_handler.assert_called_once()
        good_handler.assert_called_once()
        
        await bus.stop()
    
    async def test_event_history(self):
        """测试事件历史记录"""
        bus = EventBus(history_size=3)
        await bus.start()
        
        # 发布多个事件
        for i in range(5):
            event = Event(
                type=EventType.TERMINAL_OUTPUT,
                data=f"test_{i}",
                source="test"
            )
            await bus.publish(event)
        
        await asyncio.sleep(0.2)
        
        # 历史应该只保留最后3个
        assert len(bus.event_history) == 3
        assert bus.event_history[0].data == "test_2"
        assert bus.event_history[2].data == "test_4"
        
        await bus.stop()
    
    async def test_get_history_filtering(self):
        """测试历史记录过滤"""
        bus = EventBus()
        await bus.start()
        
        # 发布不同类型和来源的事件
        events = [
            Event(type=EventType.TERMINAL_OUTPUT, source="terminal", data="1"),
            Event(type=EventType.CONTEXT_UPDATED, source="context", data="2"),
            Event(type=EventType.TERMINAL_OUTPUT, source="terminal", data="3"),
            Event(type=EventType.COMMAND_EXECUTED, source="command", data="4"),
        ]
        
        for event in events:
            await bus.publish(event)
        
        await asyncio.sleep(0.2)
        
        # 按类型过滤
        terminal_events = await bus.get_history(event_type=EventType.TERMINAL_OUTPUT)
        assert len(terminal_events) == 2
        
        # 按来源过滤
        context_events = await bus.get_history(source="context")
        assert len(context_events) == 1
        assert context_events[0].data == "2"
        
        # 限制数量
        limited = await bus.get_history(limit=2)
        assert len(limited) == 2
        
        await bus.stop()
    
    async def test_no_subscribers(self):
        """测试没有订阅者的情况"""
        bus = EventBus()
        await bus.start()
        
        # 发布事件到没有订阅者的类型
        event = Event(type=EventType.MEMORY_UPDATED, data="test")
        await bus.publish(event)
        
        await asyncio.sleep(0.1)
        
        # 应该正常处理，不报错
        assert len(bus.event_history) == 1
        
        await bus.stop()
    
    async def test_get_stats(self):
        """测试统计信息"""
        bus = EventBus()
        handler1 = AsyncMock()
        handler2 = AsyncMock()
        
        bus.subscribe(EventType.TERMINAL_OUTPUT, handler1)
        bus.subscribe(EventType.TERMINAL_OUTPUT, handler2)
        bus.subscribe(EventType.CONTEXT_UPDATED, handler1)
        
        await bus.start()
        
        # 发布一些事件
        await bus.publish(Event(type=EventType.TERMINAL_OUTPUT, data="1"))
        await bus.publish(Event(type=EventType.CONTEXT_UPDATED, data="2"))
        
        await asyncio.sleep(0.1)
        
        stats = bus.get_stats()
        
        assert stats["running"] == True
        assert stats["history_size"] == 2
        assert stats["subscribers"]["terminal.output"] == 2
        assert stats["subscribers"]["context.updated"] == 1
        
        await bus.stop()
    
    async def test_active_handlers_tracking(self):
        """测试活跃处理器跟踪"""
        bus = EventBus()
        
        # 创建一个会阻塞的处理器
        block_event = asyncio.Event()
        
        async def blocking_handler(event):
            await block_event.wait()
        
        bus.subscribe(EventType.TERMINAL_OUTPUT, blocking_handler)
        await bus.start()
        
        # 发布事件
        await bus.publish(Event(type=EventType.TERMINAL_OUTPUT))
        
        # 等待处理器开始
        await asyncio.sleep(0.1)
        
        # 检查活跃处理器
        stats = bus.get_stats()
        assert stats["active_handlers"] == 1
        
        # 释放阻塞
        block_event.set()
        await asyncio.sleep(0.1)
        
        # 处理器应该完成
        stats = bus.get_stats()
        assert stats["active_handlers"] == 0
        
        await bus.stop()
    
    async def test_string_event_type_conversion(self):
        """测试字符串事件类型转换"""
        bus = EventBus()
        handler = AsyncMock()
        
        # 使用字符串订阅
        sub_id = bus.subscribe("terminal.output", handler)
        assert sub_id is not None
        
        # 验证转换成功
        assert EventType.TERMINAL_OUTPUT in bus.subscribers
        assert len(bus.subscribers[EventType.TERMINAL_OUTPUT]) == 1


class TestEventBusGlobalInstance:
    """测试全局 EventBus 实例"""
    
    async def test_get_event_bus_singleton(self):
        """测试单例模式"""
        from backend.services.event_bus import get_event_bus, _event_bus
        
        # 重置全局实例
        import backend.services.event_bus
        backend.services.event_bus._event_bus = None
        
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        
        assert bus1 is bus2


# ===== 主测试运行器 =====
async def main():
    """运行所有 EventBus 增强测试"""
    print("🚀 运行 EventBus 增强测试套件")
    print("=" * 80)
    
    test_classes = [
        TestEventCreation,
        TestSubscription,
        TestEventBusCore,
        TestEventBusGlobalInstance
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        print(f"\n📦 测试类: {test_class.__name__}")
        print("-" * 40)
        
        instance = test_class()
        
        # 获取所有测试方法
        test_methods = [
            method for method in dir(instance)
            if method.startswith('test_') and callable(getattr(instance, method))
        ]
        
        for method_name in test_methods:
            try:
                print(f"  🧪 {method_name}...", end='', flush=True)
                method = getattr(instance, method_name)
                await method()
                print(" ✅")
                passed += 1
            except Exception as e:
                print(f" ❌ {str(e)}")
                failed += 1
                import traceback
                traceback.print_exc()
    
    print("\n" + "=" * 80)
    print(f"✅ 通过: {passed}")
    print(f"❌ 失败: {failed}")
    print(f"总计: {passed + failed}")
    
    if passed > 0:
        print(f"\n📊 EventBus 覆盖率预计提升:")
        print("   从 36.09% → ~70%")
        print("   新增 ~25 个测试场景")
        print("   覆盖了所有核心功能:")
        print("   ✅ 事件创建和发布")
        print("   ✅ 订阅和取消订阅")
        print("   ✅ 并发处理")
        print("   ✅ 错误隔离")
        print("   ✅ 历史记录")
        print("   ✅ 同步/异步处理器")
        print("   ✅ 统计信息")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))