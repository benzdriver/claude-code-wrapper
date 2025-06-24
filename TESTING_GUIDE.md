# Claude Code Wrapper 测试指南

## 快速开始

### 运行所有测试
```bash
# 使用 Makefile
make test-all

# 或直接运行
python run_tests.py
```

### 查看测试覆盖率
```bash
# 生成覆盖率报告
make test-coverage

# 生成 HTML 覆盖率报告
make test-coverage-html
# 报告位于: htmlcov/index.html
```

## 测试结构

```
tests/
├── unit/                    # 单元测试
│   ├── api/                # API 相关测试
│   ├── services/           # 服务层测试
│   └── config/             # 配置测试
├── integration/            # 集成测试
│   ├── memory/            # Memory 子系统
│   └── embedders/         # 嵌入器测试
└── comprehensive/          # 综合测试（新增）
    └── unit/
        ├── api/           # API 完整测试
        └── services/      # 服务增强测试
```

## 新增的测试文件

### 1. API 层测试
- **文件**: `tests/comprehensive/unit/api/test_api_comprehensive.py`
- **覆盖**: WebSocket 和 REST API
- **测试数**: 15个
- **运行**: 
  ```bash
  python tests/comprehensive/unit/api/test_api_comprehensive.py
  ```

### 2. 命令管理测试
- **文件**: `tests/comprehensive/unit/services/test_command_manager_comprehensive.py`
- **覆盖**: 命令验证、执行、历史
- **测试数**: 24个
- **运行**: 
  ```bash
  python tests/comprehensive/unit/services/test_command_manager_comprehensive.py
  ```

### 3. EventBus 测试
- **文件**: `tests/comprehensive/unit/services/test_event_bus_enhanced.py`
- **覆盖**: 事件发布订阅、并发处理
- **测试数**: 23个
- **运行**: 
  ```bash
  python tests/comprehensive/unit/services/test_event_bus_enhanced.py
  ```

### 4. TerminalBridge 测试
- **文件**: `tests/comprehensive/unit/services/test_terminal_bridge_enhanced.py`
- **覆盖**: PTY 管理、命令执行
- **测试数**: 29个
- **运行**: 
  ```bash
  python tests/comprehensive/unit/services/test_terminal_bridge_enhanced.py
  ```

### 5. ContextMonitor 测试
- **文件**: `tests/comprehensive/unit/services/test_context_monitor_enhanced.py`
- **覆盖**: JSONL 解析、状态跟踪
- **测试数**: 30个
- **运行**: 
  ```bash
  python tests/comprehensive/unit/services/test_context_monitor_enhanced.py
  ```

### 6. Memory 子系统测试
- **文件**: `tests/comprehensive/unit/services/test_memory_lightweight_enhanced.py`
- **覆盖**: 内存存储、嵌入管理
- **测试数**: 11个
- **运行**: 
  ```bash
  python tests/comprehensive/unit/services/test_memory_lightweight_enhanced.py
  ```

## 编写新测试

### 1. 基本结构
```python
#!/usr/bin/env python3
"""模块描述"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))

from unittest.mock import Mock, AsyncMock, patch
import asyncio

class TestYourModule:
    """测试类"""
    
    async def test_feature(self):
        """测试某个功能"""
        # 测试代码
        assert result == expected
```

### 2. Mock 策略

#### WebSocket Mock
```python
mock_websocket = Mock()
mock_websocket.client_state = WebSocketState.CONNECTED
mock_websocket.application_state = WebSocketState.CONNECTED
```

#### 异步函数 Mock
```python
mock_func = AsyncMock(return_value="result")
```

#### 文件系统 Mock
```python
with patch('pathlib.Path.exists', return_value=True):
    # 测试代码
```

### 3. 常见模式

#### 测试异步代码
```python
async def test_async_function():
    result = await async_function()
    assert result == expected
```

#### 测试事件处理
```python
async def test_event_handler():
    bus = EventBus()
    handler_called = False
    
    async def handler(event):
        nonlocal handler_called
        handler_called = True
    
    bus.subscribe(EventType.TEST, handler)
    await bus.publish(Event(type=EventType.TEST))
    assert handler_called
```

## 测试最佳实践

### 1. 测试命名
- 使用描述性名称：`test_send_command_when_not_ready_raises_error`
- 遵循模式：`test_<功能>_<条件>_<预期结果>`

### 2. 测试隔离
- 每个测试独立运行
- 避免测试间依赖
- 清理测试产生的副作用

### 3. Mock 使用
- 只 mock 外部依赖
- 保持 mock 简单
- 验证 mock 调用

### 4. 断言
- 使用明确的断言
- 一个测试一个关注点
- 提供有意义的错误信息

## 调试测试

### 查看详细输出
```bash
# 运行单个测试文件
python -v tests/comprehensive/unit/services/test_event_bus_enhanced.py

# 使用 pytest（如果安装）
pytest -v tests/comprehensive/unit/services/test_event_bus_enhanced.py
```

### 调试失败的测试
1. 检查 mock 配置
2. 验证异步代码执行
3. 确认测试隔离
4. 查看完整的错误堆栈

## 持续集成

### GitHub Actions 配置
```yaml
- name: Run tests
  run: |
    python run_tests.py
    
- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## 常见问题

### Q: 测试运行很慢？
A: 检查是否有实际的网络调用或文件 I/O，确保都被 mock。

### Q: Mock 相关错误？
A: 确保在导入被测试模块前设置好所有 mock。

### Q: 异步测试失败？
A: 使用 `async def` 和 `await`，确保事件循环正确运行。

### Q: 覆盖率不准确？
A: 运行 `make clean` 清理缓存，然后重新运行测试。

## 维护检查表

- [ ] 新功能添加相应测试
- [ ] 修复 bug 时添加回归测试
- [ ] 定期运行完整测试套件
- [ ] 保持测试覆盖率 > 55%
- [ ] 更新测试文档

---

最后更新: 2025-06-23