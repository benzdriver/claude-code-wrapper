#!/usr/bin/env python3
"""
MemoryManager 完整测试套件
目标：提升 MemoryManager 覆盖率到 80%+
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest


import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, mock_open
from datetime import datetime
from pathlib import Path
import re

# Mock 外部依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()
sys.modules['aiofiles'] = MagicMock()


# ===== MemoryFile 和相关数据类测试 =====
@pytest.mark.asyncio
async def test_memory_file():
    """测试 MemoryFile 数据类"""
    from backend.services.memory_manager import MemoryFile
    from backend.models.base import MemoryLevel
    
    memory = MemoryFile(
        id="mem_user_CLAUDE.md",
        path=Path("/home/user/CLAUDE.md"),
        level=MemoryLevel.USER,
        content="# Test Memory\n\n@./imports/test.md",
        imports=["./imports/test.md"],
        size_bytes=1024,
        last_modified=datetime.now(),
        is_active=True,
        metadata={"line_count": 3, "has_imports": True}
    )
    
    assert memory.id == "mem_user_CLAUDE.md"
    assert memory.level == MemoryLevel.USER
    assert len(memory.imports) == 1
    assert memory.is_active == True
    assert memory.metadata["has_imports"] == True


@pytest.mark.asyncio
async def test_search_result():
    """测试 SearchResult 数据类"""
    from backend.services.memory_manager import SearchResult
    
    result = SearchResult(
        memory_id="mem_1",
        file_path="/test/CLAUDE.md",
        line_number=10,
        content="Test content line",
        score=0.85,
        context="Line before\nTest content line\nLine after"
    )
    
    assert result.memory_id == "mem_1"
    assert result.line_number == 10
    assert result.score == 0.85
    assert "Line before" in result.context


@pytest.mark.asyncio
async def test_search_options():
    """测试 SearchOptions 数据类"""
    from backend.services.memory_manager import SearchOptions
    from backend.models.base import MemoryLevel
    
    # 默认选项
    options = SearchOptions()
    assert options.use_regex == False
    assert options.case_sensitive == False
    assert options.whole_word == False
    assert options.limit == 10
    
    # 自定义选项
    options = SearchOptions(
        levels=[MemoryLevel.USER, MemoryLevel.PROJECT],
        use_regex=True,
        case_sensitive=True,
        whole_word=True,
        limit=20
    )
    assert len(options.levels) == 2
    assert options.use_regex == True
    assert options.limit == 20


# ===== MemoryManager 初始化测试 =====
@pytest.mark.asyncio
async def test_memory_manager_init():
    """测试 MemoryManager 初始化"""
    from backend.services.memory_manager import MemoryManager
    
    # 默认初始化
    manager = MemoryManager()
    assert manager.project_root == Path.cwd()
    assert manager.event_bus is not None
    assert len(manager._memory_cache) == 0
    assert len(manager._import_cache) == 0
    
    # 指定项目根目录
    project_root = Path("/test/project")
    manager = MemoryManager(project_root)
    assert manager.project_root == project_root


@pytest.mark.asyncio
async def test_memory_manager_initialize():
    """测试 MemoryManager 异步初始化"""
    from backend.services.memory_manager import MemoryManager
    
    manager = MemoryManager()
    
    with patch('backend.services.memory_manager.get_cache_manager') as mock_get_cache:
        mock_cache = AsyncMock()
        mock_get_cache.return_value = mock_cache
        
        await manager.initialize()
        
        assert manager.cache_manager == mock_cache
        mock_get_cache.assert_called_once()


# ===== 内存文件扫描测试 =====
@pytest.mark.asyncio
async def test_scan_hierarchy():
    """测试扫描内存文件层次结构"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager(Path("/test/project"))
    
    # Mock 各级内存扫描
    mock_user_memory = Mock(spec=MemoryFile)
    mock_project_memory = Mock(spec=MemoryFile)
    mock_local_memory = Mock(spec=MemoryFile)
    
    manager._scan_user_memory = AsyncMock(return_value=mock_user_memory)
    manager._scan_project_memory = AsyncMock(return_value=mock_project_memory)
    manager._scan_local_memory = AsyncMock(return_value=mock_local_memory)
    
    memories = await manager.scan_hierarchy()
    
    assert len(memories) == 3
    assert mock_user_memory in memories
    assert mock_project_memory in memories
    assert mock_local_memory in memories


@pytest.mark.asyncio
async def test_scan_user_memory():
    """测试扫描用户级内存"""
    from backend.services.memory_manager import MemoryManager
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    
    # Mock settings
    with patch('backend.services.memory_manager.settings') as mock_settings:
        mock_settings.claude_home = Path("/home/user/.claude")
        
        # 文件不存在
        with patch.object(Path, 'exists', return_value=False):
            result = await manager._scan_user_memory()
            assert result is None
        
        # 文件存在
        with patch.object(Path, 'exists', return_value=True):
            mock_memory = Mock()
            manager._load_memory_file = AsyncMock(return_value=mock_memory)
            
            result = await manager._scan_user_memory()
            assert result == mock_memory
            manager._load_memory_file.assert_called_once_with(
                Path("/home/user/.claude/CLAUDE.md"),
                MemoryLevel.USER
            )


@pytest.mark.asyncio
async def test_scan_project_memory():
    """测试扫描项目级内存"""
    from backend.services.memory_manager import MemoryManager
    from backend.models.base import MemoryLevel
    
    # 创建模拟的目录结构
    # /workspace/project/subdir (当前目录)
    # /workspace/project/CLAUDE.md (项目内存)
    # /workspace/CLAUDE.md (上级内存)
    
    current_dir = Path("/workspace/project/subdir")
    project_dir = Path("/workspace/project")
    workspace_dir = Path("/workspace")
    
    manager = MemoryManager(current_dir)
    
    # Mock Path 操作
    def mock_exists(self):
        if str(self) == "/workspace/project/subdir/CLAUDE.md":
            return False
        elif str(self) == "/workspace/project/CLAUDE.md":
            return True
        return False
    
    with patch.object(Path, 'exists', mock_exists):
        mock_memory = Mock()
        manager._load_memory_file = AsyncMock(return_value=mock_memory)
        
        result = await manager._scan_project_memory()
        assert result == mock_memory
        manager._load_memory_file.assert_called_once_with(
            project_dir / "CLAUDE.md",
            MemoryLevel.PROJECT
        )


@pytest.mark.asyncio
async def test_scan_local_memory():
    """测试扫描本地级内存"""
    from backend.services.memory_manager import MemoryManager
    from backend.models.base import MemoryLevel
    
    project_dir = Path("/test/project")
    manager = MemoryManager(project_dir)
    
    # 文件不存在
    with patch.object(Path, 'exists', return_value=False):
        result = await manager._scan_local_memory()
        assert result is None
    
    # 文件存在
    with patch.object(Path, 'exists', return_value=True):
        mock_memory = Mock()
        manager._load_memory_file = AsyncMock(return_value=mock_memory)
        
        result = await manager._scan_local_memory()
        assert result == mock_memory
        manager._load_memory_file.assert_called_once_with(
            project_dir / "CLAUDE.local.md",
            MemoryLevel.LOCAL
        )


# ===== 内存文件加载测试 =====
@pytest.mark.asyncio
async def test_load_memory_file():
    """测试加载内存文件"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel, EventType
    
    manager = MemoryManager()
    manager.cache_manager = AsyncMock()
    manager.event_bus = AsyncMock()
    
    test_path = Path("/test/CLAUDE.md")
    test_content = "# Test Memory\n\n@./imports/test.md\n\nSome content"
    
    # Mock 文件操作
    mock_stat = Mock()
    mock_stat.st_size = 1024
    mock_stat.st_mtime = 1234567890
    
    # 创建异步文件读取 mock
    class AsyncFileMock:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def read(self):
            return test_content
    
    with patch('backend.services.memory_manager.aiofiles.open', return_value=AsyncFileMock()):
        with patch.object(Path, 'stat', return_value=mock_stat):
            # 缓存未命中
            manager.cache_manager.get_memory_content.return_value = None
            
            result = await manager._load_memory_file(test_path, MemoryLevel.USER)
            
            assert isinstance(result, MemoryFile)
            assert result.path == test_path
            assert result.level == MemoryLevel.USER
            assert result.content == test_content
            assert len(result.imports) == 1
            assert result.imports[0] == "./imports/test.md"
            assert result.size_bytes == 1024
            
            # 验证缓存设置
            manager.cache_manager.set_memory_content.assert_called_once_with(
                str(test_path), test_content
            )
            
            # 验证事件发布
            manager.event_bus.publish.assert_called_once()
            event = manager.event_bus.publish.call_args[0][0]
            assert event.type == EventType.MEMORY_UPDATED


@pytest.mark.asyncio
async def test_load_memory_file_with_cache():
    """测试从缓存加载内存文件"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    manager.cache_manager = AsyncMock()
    
    test_path = Path("/test/CLAUDE.md")
    cached_content = "# Cached content"
    
    # Mock 缓存命中
    manager.cache_manager.get_memory_content.return_value = cached_content
    
    # 设置内存缓存
    mock_memory = Mock(spec=MemoryFile)
    manager._memory_cache[str(test_path)] = {
        'memory': mock_memory,
        'mtime': 1234567890
    }
    
    # Mock stat
    mock_stat = Mock()
    mock_stat.st_mtime = 1234567890  # 相同的修改时间
    
    with patch.object(Path, 'stat', return_value=mock_stat):
        result = await manager._load_memory_file(test_path, MemoryLevel.USER)
        assert result == mock_memory


# ===== 内容管理测试 =====
@pytest.mark.asyncio
async def test_get_memory():
    """测试获取特定内存文件"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    
    manager = MemoryManager()
    
    # Mock 内存文件
    mock_memory1 = Mock(spec=MemoryFile, id="mem_1")
    mock_memory2 = Mock(spec=MemoryFile, id="mem_2")
    mock_memory3 = Mock(spec=MemoryFile, id="mem_3")
    
    manager.scan_hierarchy = AsyncMock(return_value=[mock_memory1, mock_memory2, mock_memory3])
    
    # 找到内存
    result = await manager.get_memory("mem_2")
    assert result == mock_memory2
    
    # 未找到内存
    result = await manager.get_memory("mem_not_exist")
    assert result is None


@pytest.mark.asyncio
async def test_add_content_new_file():
    """测试向新文件添加内容"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager(Path("/test/project"))
    
    target_path = Path("/test/project/CLAUDE.md")
    
    # Mock 文件不存在
    with patch.object(Path, 'exists', return_value=False):
        # Mock aiofiles.open
        written_content = []
        
        class AsyncWriteMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def write(self, content):
                written_content.append(content)
        
        with patch('backend.services.memory_manager.aiofiles.open', return_value=AsyncWriteMock()):
            # Mock _load_memory_file
            mock_memory = Mock(spec=MemoryFile)
            manager._load_memory_file = AsyncMock(return_value=mock_memory)
            manager.cache_manager = AsyncMock()
            
            result = await manager.add_content("Test content", MemoryLevel.PROJECT, "Test Section")
            
            assert result == mock_memory
            assert len(written_content) == 1
            assert "# Claude Memory - Project Level" in written_content[0]
            assert "## Test Section" in written_content[0]
            assert "Test content" in written_content[0]


@pytest.mark.asyncio
async def test_add_content_existing_file():
    """测试向现有文件添加内容"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    
    existing_content = "# Existing Memory\n\n## Section 1\nContent 1\n"
    
    # Mock 现有内存
    mock_memory = Mock(spec=MemoryFile)
    mock_memory.content = existing_content
    
    # Mock 文件存在
    with patch.object(Path, 'exists', return_value=True):
        manager._load_memory_file = AsyncMock(return_value=mock_memory)
        manager.cache_manager = AsyncMock()
        
        written_content = []
        
        class AsyncWriteMock:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass
            async def write(self, content):
                written_content.append(content)
        
        with patch('backend.services.memory_manager.aiofiles.open', return_value=AsyncWriteMock()):
            # 添加到新节
            result = await manager.add_content("New content", MemoryLevel.USER, "Section 2")
            
            assert len(written_content) == 1
            assert "## Section 1" in written_content[0]
            assert "## Section 2" in written_content[0]
            assert "New content" in written_content[0]


# ===== 搜索功能测试 =====
@pytest.mark.asyncio
async def test_search_basic():
    """测试基本搜索功能"""
    from backend.services.memory_manager import MemoryManager, MemoryFile, SearchOptions, SearchResult
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    manager.event_bus = AsyncMock()
    
    # Mock 内存文件
    memory1 = Mock(spec=MemoryFile)
    memory1.id = "mem_1"
    memory1.path = Path("/test/CLAUDE.md")
    memory1.level = MemoryLevel.USER
    
    memory2 = Mock(spec=MemoryFile)
    memory2.id = "mem_2"
    memory2.path = Path("/test/project/CLAUDE.md")
    memory2.level = MemoryLevel.PROJECT
    
    manager.scan_hierarchy = AsyncMock(return_value=[memory1, memory2])
    
    # Mock resolve_imports
    content1 = "Line 1\nThis is a test line\nLine 3"
    content2 = "Another file\nThis is also a test\nEnd"
    
    async def mock_resolve(memory):
        if memory == memory1:
            return content1
        return content2
    
    manager.resolve_imports = mock_resolve
    
    # 执行搜索
    results = await manager.search("test")
    
    assert len(results) == 2
    assert all(isinstance(r, SearchResult) for r in results)
    assert results[0].content == "This is a test line"
    assert results[1].content == "This is also a test"


@pytest.mark.asyncio
async def test_search_with_options():
    """测试带选项的搜索"""
    from backend.services.memory_manager import MemoryManager, MemoryFile, SearchOptions
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    manager.event_bus = AsyncMock()
    
    # Mock 内存文件
    memory1 = Mock(spec=MemoryFile)
    memory1.id = "mem_1"
    memory1.path = Path("/test/user/CLAUDE.md")
    memory1.level = MemoryLevel.USER
    
    memory2 = Mock(spec=MemoryFile)
    memory2.id = "mem_2"
    memory2.path = Path("/test/project/CLAUDE.md")
    memory2.level = MemoryLevel.PROJECT
    
    memory3 = Mock(spec=MemoryFile)
    memory3.id = "mem_3"
    memory3.path = Path("/test/local/CLAUDE.local.md")
    memory3.level = MemoryLevel.LOCAL
    
    manager.scan_hierarchy = AsyncMock(return_value=[memory1, memory2, memory3])
    manager.resolve_imports = AsyncMock(return_value="test content")
    
    # 只搜索特定级别
    options = SearchOptions(
        levels=[MemoryLevel.USER, MemoryLevel.PROJECT],
        limit=5
    )
    
    results = await manager.search("test", options)
    
    # 验证级别过滤
    manager.resolve_imports.assert_any_call(memory1)
    manager.resolve_imports.assert_any_call(memory2)
    # LOCAL 级别不应被搜索
    assert memory3 not in [call[0][0] for call in manager.resolve_imports.call_args_list]


@pytest.mark.asyncio
async def test_search_regex():
    """测试正则表达式搜索"""
    from backend.services.memory_manager import MemoryManager, MemoryFile, SearchOptions
    
    manager = MemoryManager()
    manager.event_bus = AsyncMock()
    
    memory = Mock(spec=MemoryFile)
    memory.id = "mem_1"
    memory.path = Path("/test/CLAUDE.md")
    
    manager.scan_hierarchy = AsyncMock(return_value=[memory])
    manager.resolve_imports = AsyncMock(return_value="test123\ntest_abc\nno match")
    
    # 使用正则表达式
    options = SearchOptions(use_regex=True)
    results = await manager.search(r"test\d+", options)
    
    assert len(results) == 1
    assert results[0].content == "test123"


@pytest.mark.asyncio
async def test_search_whole_word():
    """测试全词匹配搜索"""
    from backend.services.memory_manager import MemoryManager, MemoryFile, SearchOptions
    
    manager = MemoryManager()
    manager.event_bus = AsyncMock()
    
    memory = Mock(spec=MemoryFile)
    memory.id = "mem_1"
    memory.path = Path("/test/CLAUDE.md")
    manager.scan_hierarchy = AsyncMock(return_value=[memory])
    manager.resolve_imports = AsyncMock(return_value="test testing\nthis is a test case\ntested")
    
    # 全词匹配
    options = SearchOptions(whole_word=True)
    results = await manager.search("test", options)
    
    assert len(results) == 2
    assert "test testing" in results[0].content
    assert "this is a test case" in results[1].content
    # "tested" 不应匹配


# ===== 导入解析测试 =====
@pytest.mark.asyncio
async def test_resolve_imports_basic():
    """测试基本导入解析"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    manager.event_bus = AsyncMock()
    
    # 主内存文件
    memory = MemoryFile(
        id="mem_1",
        path=Path("/test/CLAUDE.md"),
        level=MemoryLevel.PROJECT,
        content="# Main\n\n@./imports/test.md\n\nEnd",
        imports=["./imports/test.md"]
    )
    
    # Mock 导入文件内容
    imported_content = "# Imported content\nThis is imported"
    
    class AsyncReadMock:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def read(self):
            return imported_content
    
    with patch('backend.services.memory_manager.aiofiles.open', return_value=AsyncReadMock()):
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'resolve', return_value=Path("/test/imports/test.md")):
                result = await manager.resolve_imports(memory)
    
    assert "# Main" in result
    assert "# Imported from ./imports/test.md" in result
    assert "This is imported" in result
    assert "# End import ./imports/test.md" in result


@pytest.mark.asyncio
async def test_resolve_imports_circular():
    """测试循环导入检测"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    
    # 创建循环导入场景
    memory = MemoryFile(
        id="mem_1",
        path=Path("/test/CLAUDE.md"),
        level=MemoryLevel.PROJECT,
        content="@./other.md",
        imports=["./other.md"]
    )
    
    # 模拟已经访问过
    seen = {str(memory.path)}
    
    result = await manager.resolve_imports(memory, _seen=seen)
    
    assert "# Circular import: /test/CLAUDE.md" in result


@pytest.mark.asyncio
async def test_resolve_imports_not_found():
    """测试导入文件不存在"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    
    memory = MemoryFile(
        id="mem_1",
        path=Path("/test/CLAUDE.md"),
        level=MemoryLevel.PROJECT,
        content="@./missing.md",
        imports=["./missing.md"]
    )
    
    with patch.object(Path, 'exists', return_value=False):
        result = await manager.resolve_imports(memory)
    
    assert "# Import not found: ./missing.md" in result


@pytest.mark.asyncio
async def test_resolve_imports_nested():
    """测试嵌套导入解析"""
    from backend.services.memory_manager import MemoryManager, MemoryFile
    from backend.models.base import MemoryLevel
    
    manager = MemoryManager()
    manager.event_bus = AsyncMock()
    
    # 主文件
    memory = MemoryFile(
        id="mem_1",
        path=Path("/test/CLAUDE.md"),
        level=MemoryLevel.PROJECT,
        content="@./level1.md",
        imports=["./level1.md"]
    )
    
    # 模拟文件内容
    file_contents = {
        "/test/level1.md": "@./level2.md\nLevel 1 content",
        "/test/level2.md": "Level 2 content"
    }
    
    class AsyncReadMock:
        def __init__(self, path):
            self.path = str(path)
            
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def read(self):
            return file_contents.get(self.path, "")
    
    def mock_open(path, *args, **kwargs):
        return AsyncReadMock(path)
    
    with patch('backend.services.memory_manager.aiofiles.open', side_effect=mock_open):
        with patch.object(Path, 'exists', return_value=True):
            result = await manager.resolve_imports(memory)
    
    assert "Level 1 content" in result
    assert "Level 2 content" in result


# ===== 统计信息测试 =====
@pytest.mark.asyncio
async def test_get_stats():
    """测试获取统计信息"""
    from backend.services.memory_manager import MemoryManager
    
    manager = MemoryManager(Path("/test/project"))
    
    # 设置一些缓存数据
    manager._memory_cache = {"file1": {}, "file2": {}}
    manager._import_cache = {"import1": "", "import2": "", "import3": ""}
    
    stats = manager.get_stats()
    
    assert stats["memories_cached"] == 2
    assert stats["imports_resolved"] == 3
    assert stats["project_root"] == "/test/project"


# ===== 工厂函数测试 =====
@pytest.mark.asyncio
async def test_create_memory_manager():
    """测试工厂函数"""
    from backend.services.memory_manager import create_memory_manager
    
    # 默认创建
    manager = create_memory_manager()
    assert manager.project_root == Path.cwd()
    
    # 指定项目根目录
    project_root = Path("/custom/project")
    manager = create_memory_manager(project_root)
    assert manager.project_root == project_root


# ===== 主测试运行器 =====
async def main():
    """运行所有测试"""
    print("🚀 运行 MemoryManager 完整测试套件")
    print("=" * 80)
    
    tests = [
        # 数据类测试
        test_memory_file,
        test_search_result,
        test_search_options,
        
        # 初始化测试
        test_memory_manager_init,
        test_memory_manager_initialize,
        
        # 扫描测试
        test_scan_hierarchy,
        test_scan_user_memory,
        test_scan_project_memory,
        test_scan_local_memory,
        
        # 加载测试
        test_load_memory_file,
        test_load_memory_file_with_cache,
        
        # 内容管理
        test_get_memory,
        test_add_content_new_file,
        test_add_content_existing_file,
        
        # 搜索功能
        test_search_basic,
        test_search_with_options,
        test_search_regex,
        test_search_whole_word,
        
        # 导入解析
        test_resolve_imports_basic,
        test_resolve_imports_circular,
        test_resolve_imports_not_found,
        test_resolve_imports_nested,
        
        # 其他
        test_get_stats,
        test_create_memory_manager
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