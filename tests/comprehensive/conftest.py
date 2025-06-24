"""
Pytest 配置和共享 fixtures
"""
import asyncio
import sys
import os
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock
import pytest

# 确保可以导入项目模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Mock 外部依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()
sys.modules['watchdog'] = MagicMock()
sys.modules['watchdog.observers'] = MagicMock()
sys.modules['watchdog.events'] = MagicMock()
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()

# FastAPI 相关 Mock - 需要更详细的设置
fastapi_mock = MagicMock()
sys.modules['fastapi'] = fastapi_mock

# WebSocket 相关
websocket_mock = MagicMock()
websocket_disconnect_mock = MagicMock()
query_mock = MagicMock()

fastapi_mock.WebSocket = websocket_mock
fastapi_mock.WebSocketDisconnect = websocket_disconnect_mock
fastapi_mock.Query = query_mock

# WebSocketState Mock
websocket_state_mock = MagicMock()
websocket_state_mock.DISCONNECTED = 'disconnected'
websocket_state_mock.CONNECTED = 'connected'
websocket_state_mock.CONNECTING = 'connecting'

# 创建 fastapi.websockets 模块
fastapi_websockets_mock = MagicMock()
fastapi_websockets_mock.WebSocketState = websocket_state_mock
sys.modules['fastapi.websockets'] = fastapi_websockets_mock

# 其他 Mock
sys.modules['sentence_transformers'] = MagicMock()
sys.modules['openai'] = MagicMock()
sys.modules['qdrant_client'] = MagicMock()
sys.modules['numpy'] = MagicMock()
sys.modules['websockets'] = MagicMock()
sys.modules['httpx'] = MagicMock()


# ===== 通用 Fixtures =====

@pytest.fixture
def event_loop():
    """创建事件循环"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def mock_event_bus():
    """模拟事件总线"""
    from backend.services.event_bus import EventBus
    bus = EventBus()
    await bus.start()
    yield bus
    await bus.stop()


@pytest.fixture
def mock_cache_manager():
    """模拟缓存管理器"""
    manager = Mock()
    manager.get = AsyncMock(return_value=None)
    manager.set = AsyncMock()
    manager.delete = AsyncMock()
    manager.clear = AsyncMock()
    manager.get_stats = Mock(return_value={
        'hits': 0,
        'misses': 0,
        'sets': 0,
        'deletes': 0,
        'hit_rate': 0.0
    })
    return manager


@pytest.fixture
def mock_settings():
    """模拟配置对象"""
    settings = Mock()
    settings.redis_url = "redis://localhost:6379"
    settings.has_redis = False
    settings.cache_ttl = 3600
    settings.cache_max_size = 1000
    settings.claude_home = Path("/test/home")
    settings.log_level = "INFO"
    return settings


@pytest.fixture
def temp_test_dir(tmp_path):
    """创建临时测试目录"""
    test_dir = tmp_path / "test_data"
    test_dir.mkdir(exist_ok=True)
    return test_dir


# ===== 异步工具 =====

class AsyncFileMock:
    """模拟异步文件对象"""
    def __init__(self, content="", lines=None):
        self.content = content
        self.lines = lines or []
        self._line_index = 0
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, *args):
        pass
    
    async def read(self):
        return self.content
    
    async def write(self, data):
        self.content = data
    
    def __aiter__(self):
        self._line_index = 0
        return self
    
    async def __anext__(self):
        if self._line_index < len(self.lines):
            line = self.lines[self._line_index]
            self._line_index += 1
            return line
        raise StopAsyncIteration


class AsyncContextManagerMock:
    """模拟异步上下文管理器"""
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value or self
    
    async def __aexit__(self, *args):
        pass


# ===== 测试数据生成器 =====

def create_test_file_info(path="test.py", size=1000):
    """创建测试 FileInfo 对象"""
    from backend.models.base import FileInfo
    return FileInfo(
        path=path,
        size=size,
        last_modified=None,
        first_seen=None
    )


def create_test_context_state(percentage=50.0, token_count=100000):
    """创建测试 ContextState 对象"""
    from backend.services.context_monitor import ContextState
    from datetime import datetime
    
    return ContextState(
        percentage=percentage,
        token_count=token_count,
        token_limit=200000,
        model="claude-3-opus-20240229",
        files_loaded=[create_test_file_info()],
        session_start=datetime.now()
    )


# ===== Pytest 配置 =====

def pytest_configure(config):
    """配置 pytest"""
    # 注册自定义标记
    config.addinivalue_line("markers", "unit: 单元测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "e2e: 端到端测试")
    config.addinivalue_line("markers", "slow: 慢速测试")
    config.addinivalue_line("markers", "asyncio: 异步测试")


def pytest_collection_modifyitems(config, items):
    """修改测试收集"""
    for item in items:
        # 自动为异步测试添加 asyncio 标记
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.asyncio)