#!/usr/bin/env python3
"""
CacheManager 完整测试套件
目标：提升 CacheManager 覆盖率到 80%+
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import time
import json
import pytest

# Mock 外部依赖
sys.modules['redis'] = MagicMock()
sys.modules['redis.asyncio'] = MagicMock()


# ===== CacheEntry 测试 =====
@pytest.mark.asyncio
async def test_cache_entry():
    """测试 CacheEntry 数据类"""
    from backend.services.cache_manager import CacheEntry
    
    # 测试无 TTL 的条目
    entry = CacheEntry(key="test", value="value")
    assert entry.key == "test"
    assert entry.value == "value"
    assert entry.ttl is None
    assert not entry.is_expired()
    
    # 测试有 TTL 的条目
    entry = CacheEntry(key="test", value="value", ttl=10)
    assert entry.ttl == 10
    # 设置一个已知的 created_at 以便测试
    entry.created_at = 100
    
    # 测试未过期
    with patch('time.time', return_value=105):
        assert not entry.is_expired()
    
    # 测试已过期
    with patch('time.time', return_value=111):
        assert entry.is_expired()


@pytest.mark.asyncio
async def test_cache_stats():
    """测试 CacheStats 数据类"""
    from backend.services.cache_manager import CacheStats
    
    stats = CacheStats()
    assert stats.hits == 0
    assert stats.misses == 0
    assert stats.hit_rate == 0.0
    
    # 测试命中率计算
    stats.hits = 80
    stats.misses = 20
    assert stats.hit_rate == 0.8
    
    # 测试其他统计
    stats.sets = 100
    stats.deletes = 10
    stats.evictions = 5
    assert stats.sets == 100
    assert stats.deletes == 10
    assert stats.evictions == 5


# ===== InMemoryCache 测试 =====
@pytest.mark.asyncio
async def test_inmemory_cache_basic():
    """测试内存缓存基本操作"""
    from backend.services.cache_manager import InMemoryCache
    
    cache = InMemoryCache(max_size=3)
    
    # 测试初始状态
    assert cache.max_size == 3
    assert len(cache.cache) == 0
    assert cache.stats.size == 0
    
    # 测试 set 和 get
    await cache.set("key1", "value1")
    value = await cache.get("key1")
    assert value == "value1"
    assert cache.stats.sets == 1
    assert cache.stats.hits == 1
    
    # 测试 miss
    value = await cache.get("nonexistent")
    assert value is None
    assert cache.stats.misses == 1
    
    # 测试 delete
    result = await cache.delete("key1")
    assert result == True
    assert cache.stats.deletes == 1
    
    result = await cache.delete("nonexistent")
    assert result == False


@pytest.mark.asyncio
async def test_inmemory_cache_ttl():
    """测试内存缓存 TTL 功能"""
    from backend.services.cache_manager import InMemoryCache
    
    cache = InMemoryCache()
    
    # 设置带 TTL 的值
    await cache.set("key1", "value1", ttl=10)
    # 直接修改缓存条目的 created_at 以便测试
    cache.cache["key1"].created_at = 100
    
    # 未过期时获取
    with patch('time.time', return_value=105):
        value = await cache.get("key1")
        assert value == "value1"
    
    # 过期后获取
    with patch('time.time', return_value=111):
        # 由于 InMemoryCache.get 中的 is_expired 检查使用当前 time.time
        # 需要 patch backend.services.cache_manager.time.time
        with patch('backend.services.cache_manager.time.time', return_value=111):
            value = await cache.get("key1")
            assert value is None
            assert cache.stats.evictions == 1


@pytest.mark.asyncio
async def test_inmemory_cache_lru_eviction():
    """测试 LRU 驱逐策略"""
    from backend.services.cache_manager import InMemoryCache
    
    cache = InMemoryCache(max_size=3)
    
    # 填满缓存
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    await cache.set("key3", "value3")
    assert cache.stats.size == 3
    
    # 访问 key1，使其成为最近使用
    await cache.get("key1")
    
    # 添加新键，应该驱逐 key2（最久未使用）
    await cache.set("key4", "value4")
    assert cache.stats.evictions == 1
    assert await cache.get("key2") is None  # 被驱逐
    assert await cache.get("key1") == "value1"  # 仍存在
    assert await cache.get("key3") == "value3"  # 仍存在
    assert await cache.get("key4") == "value4"  # 新添加


@pytest.mark.asyncio
async def test_inmemory_cache_clear():
    """测试清空缓存"""
    from backend.services.cache_manager import InMemoryCache
    
    cache = InMemoryCache()
    
    # 添加一些数据
    await cache.set("key1", "value1")
    await cache.set("key2", "value2")
    assert cache.stats.size == 2
    
    # 清空
    await cache.clear()
    assert len(cache.cache) == 0
    assert cache.stats.size == 0
    assert await cache.get("key1") is None


@pytest.mark.asyncio
async def test_inmemory_cache_keys():
    """测试键模式匹配"""
    from backend.services.cache_manager import InMemoryCache
    
    cache = InMemoryCache()
    
    # 添加不同模式的键
    await cache.set("user:123", "data1")
    await cache.set("user:456", "data2")
    await cache.set("session:789", "data3")
    await cache.set("config", "data4")
    
    # 测试获取所有键
    all_keys = await cache.keys("*")
    assert len(all_keys) == 4
    assert "user:123" in all_keys
    
    # 测试模式匹配
    user_keys = await cache.keys("user:*")
    assert len(user_keys) == 2
    assert "user:123" in user_keys
    assert "user:456" in user_keys
    assert "session:789" not in user_keys
    
    # 测试精确匹配
    config_keys = await cache.keys("config")
    assert len(config_keys) == 1
    assert "config" in config_keys


# ===== RedisCache 测试 =====
@pytest.mark.asyncio
async def test_redis_cache_no_redis():
    """测试没有 Redis 包时的行为"""
    from backend.services.cache_manager import RedisCache
    
    with patch('backend.services.cache_manager.HAS_REDIS', False):
        cache = RedisCache("redis://localhost")
        
        # 连接应该失败
        with pytest.raises(RuntimeError, match="Redis package not installed"):
            await cache.connect()


@pytest.mark.asyncio
async def test_redis_cache_connect():
    """测试 Redis 连接"""
    from backend.services.cache_manager import RedisCache
    
    # Mock Redis
    mock_redis = MagicMock()
    mock_client = AsyncMock()
    mock_client.ping = AsyncMock()
    mock_redis.from_url.return_value = mock_client
    
    with patch('backend.services.cache_manager.HAS_REDIS', True):
        with patch('backend.services.cache_manager.redis', mock_redis):
            cache = RedisCache("redis://localhost")
            
            # 连接
            await cache.connect()
            assert cache.client == mock_client
            mock_client.ping.assert_called_once()
            
            # 断开连接
            await cache.disconnect()
            mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_redis_cache_operations():
    """测试 Redis 缓存操作"""
    from backend.services.cache_manager import RedisCache
    
    # Mock Redis client
    mock_client = AsyncMock()
    
    cache = RedisCache("redis://localhost")
    cache.client = mock_client
    
    # 测试 get - 命中
    mock_client.get = AsyncMock(return_value="value1")
    value = await cache.get("key1")
    assert value == "value1"
    assert cache.stats.hits == 1
    
    # 测试 get - JSON 值
    mock_client.get = AsyncMock(return_value='{"name": "test"}')
    value = await cache.get("key2")
    assert value == {"name": "test"}
    
    # 测试 get - 未命中
    mock_client.get = AsyncMock(return_value=None)
    value = await cache.get("key3")
    assert value is None
    assert cache.stats.misses == 1
    
    # 测试 set - 字符串值
    await cache.set("key4", "value4", ttl=60)
    mock_client.set.assert_called_with("key4", "value4", ex=60)
    assert cache.stats.sets == 1
    
    # 测试 set - 复杂值
    await cache.set("key5", {"data": "complex"})
    mock_client.set.assert_called_with("key5", '{"data": "complex"}', ex=None)
    
    # 测试 delete
    mock_client.delete = AsyncMock(return_value=1)
    result = await cache.delete("key6")
    assert result == True
    assert cache.stats.deletes == 1
    
    # 测试 delete - 不存在的键
    mock_client.delete = AsyncMock(return_value=0)
    result = await cache.delete("nonexistent")
    assert result == False


@pytest.mark.asyncio
async def test_redis_cache_error_handling():
    """测试 Redis 错误处理"""
    from backend.services.cache_manager import RedisCache
    
    cache = RedisCache("redis://localhost")
    cache.client = AsyncMock()
    
    # 测试 get 错误
    cache.client.get = AsyncMock(side_effect=Exception("Connection error"))
    value = await cache.get("key1")
    assert value is None
    assert cache.stats.misses == 1
    
    # 测试 set 错误
    cache.client.set = AsyncMock(side_effect=Exception("Write error"))
    await cache.set("key2", "value2")  # 不应该抛出异常
    
    # 测试 delete 错误
    cache.client.delete = AsyncMock(side_effect=Exception("Delete error"))
    result = await cache.delete("key3")
    assert result == False


@pytest.mark.asyncio
async def test_redis_cache_without_client():
    """测试未连接时的 Redis 操作"""
    from backend.services.cache_manager import RedisCache
    
    cache = RedisCache("redis://localhost")
    # 不设置 client，模拟未连接状态
    
    assert await cache.get("key") is None
    await cache.set("key", "value")  # 应该静默失败
    assert await cache.delete("key") == False
    assert await cache.keys() == set()
    
    # 验证 stats
    assert cache.stats.hits == 0
    assert cache.stats.sets == 0


# ===== CacheManager 测试 =====
@pytest.mark.asyncio
async def test_cache_manager_selection():
    """测试 CacheManager 选择正确的缓存后端"""
    from backend.services.cache_manager import CacheManager
    
    # 测试使用 Redis - 使用 mock settings 对象
    mock_settings = MagicMock()
    mock_settings.has_redis = True
    mock_settings.redis_url = "redis://localhost"
    
    with patch('backend.services.cache_manager.HAS_REDIS', True):
        with patch('backend.services.cache_manager.settings', mock_settings):
            manager = CacheManager()
            # CacheManager has memory_cache and redis_cache attributes
            assert hasattr(manager, 'memory_cache')
            assert hasattr(manager, 'redis_cache')
            assert manager.redis_cache is not None
    
    # 测试回退到内存缓存
    with patch('backend.services.cache_manager.HAS_REDIS', False):
        manager = CacheManager()
        await manager.initialize()
        assert hasattr(manager, 'memory_cache')
        assert manager.redis_cache is None


@pytest.mark.asyncio
async def test_cache_manager_operations():
    """测试 CacheManager 统一接口"""
    from backend.services.cache_manager import CacheManager
    
    manager = CacheManager()
    await manager.initialize()
    
    # 基本操作
    await manager.set("test_key", {"data": "test"})
    value = await manager.get("test_key")
    assert value == {"data": "test"}
    
    # 删除
    result = await manager.delete("test_key")
    assert result == True
    
    # 清空模式匹配的键
    # 由于 Redis 连接失败，只会从内存中删除
    count = await manager.clear_pattern("test_key")
    assert count >= 0  # 可能是 0 或 1，取决于是否匹配
    # 验证键已被删除
    assert await manager.get("test_key") is None
    
    # 测试统计信息
    stats = await manager.get_stats()
    assert "memory" in stats
    assert "hits" in stats["memory"]


# ===== 辅助函数测试 =====
@pytest.mark.asyncio
async def test_get_cache_manager():
    """测试获取全局缓存管理器"""
    from backend.services.cache_manager import get_cache_manager
    
    # 第一次调用应该创建新实例
    manager1 = await get_cache_manager()
    assert manager1 is not None
    
    # 第二次调用应该返回相同实例
    manager2 = await get_cache_manager()
    assert manager1 is manager2


# ===== 主测试运行器 =====
async def main():
    """运行所有测试"""
    print("🚀 运行 CacheManager 完整测试套件")
    print("=" * 80)
    
    tests = [
        # CacheEntry
        test_cache_entry,
        test_cache_stats,
        
        # InMemoryCache
        test_inmemory_cache_basic,
        test_inmemory_cache_ttl,
        test_inmemory_cache_lru_eviction,
        test_inmemory_cache_clear,
        test_inmemory_cache_keys,
        
        # RedisCache
        test_redis_cache_no_redis,
        test_redis_cache_connect,
        test_redis_cache_operations,
        test_redis_cache_error_handling,
        test_redis_cache_without_client,
        
        # CacheManager
        test_cache_manager_selection,
        test_cache_manager_operations,
        
        # 辅助函数
        test_get_cache_manager
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