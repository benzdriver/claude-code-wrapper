#!/usr/bin/env python3
"""
TerminalBridge 完整测试套件
目标：提升 TerminalBridge 覆盖率到 70%+
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pytest


import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime
from pathlib import Path
import subprocess
import signal

# Mock 外部依赖
sys.modules['pydantic'] = MagicMock()
sys.modules['pydantic_settings'] = MagicMock()


# ===== TerminalState 测试 =====
@pytest.mark.asyncio
async def test_terminal_state():
    """测试 TerminalState 数据类"""
    from backend.services.terminal_bridge import TerminalState
    
    # 默认状态
    state = TerminalState()
    assert state.is_alive == False
    assert state.is_ready == False
    assert state.last_activity is None
    assert state.command_count == 0
    assert state.error_count == 0
    assert state.restart_count == 0
    
    # 更新状态
    state.is_alive = True
    state.command_count = 5
    state.error_count = 1
    assert state.is_alive == True
    assert state.command_count == 5
    assert state.error_count == 1


# ===== TerminalBridge 初始化测试 =====
@pytest.mark.asyncio
async def test_terminal_bridge_init():
    """测试 TerminalBridge 初始化"""
    from backend.services.terminal_bridge import TerminalBridge
    
    # 默认初始化
    bridge = TerminalBridge()
    assert bridge.workspace == Path(".").absolute()
    assert bridge.process is None
    assert bridge.master_fd is None
    assert bridge.state.is_alive == False
    assert bridge.output_callback is None
    assert bridge.output_buffer == ""
    
    # 指定工作目录
    workspace = "/test/workspace"
    bridge = TerminalBridge(workspace)
    assert bridge.workspace == Path(workspace).absolute()


@pytest.mark.asyncio
async def test_terminal_bridge_configuration():
    """测试 TerminalBridge 配置参数"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    
    # 检查默认配置
    assert bridge.startup_timeout == 10.0
    assert bridge.command_timeout == 30.0
    assert bridge.health_check_interval == 5.0
    assert bridge.max_restart_attempts == 3
    assert bridge.restart_delay == 2.0
    
    # 检查提示符模式
    assert 'claude-code>' in bridge.PROMPT_PATTERNS
    assert '$' in bridge.PROMPT_PATTERNS
    assert '>' in bridge.PROMPT_PATTERNS


# ===== 状态检查测试 =====
@pytest.mark.asyncio
async def test_is_alive():
    """测试进程存活检查"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    
    # 没有进程
    assert bridge.is_alive() == False
    
    # 有进程但已退出
    mock_process = Mock()
    mock_process.poll.return_value = 0  # 已退出
    bridge.process = mock_process
    assert bridge.is_alive() == False
    
    # 有进程且运行中
    mock_process.poll.return_value = None  # 运行中
    assert bridge.is_alive() == True


@pytest.mark.asyncio
async def test_is_running():
    """测试 is_running 属性"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    
    # 初始状态
    assert bridge.is_running == False
    
    # 设置状态
    bridge.state.is_alive = True
    mock_process = Mock()
    mock_process.poll.return_value = None
    bridge.process = mock_process
    
    assert bridge.is_running == True


@pytest.mark.asyncio
async def test_set_output_callback():
    """测试设置输出回调"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    
    def test_callback(output):
        pass
    
    bridge.set_output_callback(test_callback)
    assert bridge.output_callback == test_callback


# ===== 命令发送测试 =====
@pytest.mark.asyncio
async def test_send_command_not_started():
    """测试向未启动的终端发送命令"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    bridge.state.is_alive = False
    
    try:
        await bridge.send_command("test")
        assert False, "应该抛出异常"
    except RuntimeError as e:
        assert "Terminal not started" in str(e)


@pytest.mark.asyncio
async def test_send_command_not_ready():
    """测试向未准备好的终端发送命令"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    bridge.state.is_alive = True
    bridge.state.is_ready = False
    
    try:
        await bridge.send_command("test")
        assert False, "应该抛出异常"
    except RuntimeError as e:
        assert "Terminal not ready" in str(e)


@pytest.mark.asyncio
async def test_send_command_success():
    """测试成功发送命令"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    bridge.state.is_alive = True
    bridge.state.is_ready = True
    bridge.master_fd = 10
    
    with patch('backend.services.terminal_bridge.os.write') as mock_write:
        await bridge.send_command("echo test")
        
        # 验证写入
        mock_write.assert_called_once_with(10, b"echo test\n")
        assert bridge.state.command_count == 1
        assert bridge.state.last_activity is not None


@pytest.mark.asyncio
async def test_send_command_error():
    """测试命令发送错误"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    bridge.state.is_alive = True
    bridge.state.is_ready = True
    bridge.master_fd = 10
    
    with patch('backend.services.terminal_bridge.os.write', side_effect=OSError("Write failed")):
        try:
            await bridge.send_command("test")
            assert False, "应该抛出异常"
        except Exception:
            assert bridge.state.error_count == 1


# ===== 停止进程测试 =====
@pytest.mark.asyncio
async def test_stop_not_running():
    """测试停止未运行的进程"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    bridge.state.is_alive = False
    
    # 停止未运行的进程应该直接返回
    await bridge.stop()


# ===== 接口实现测试 =====
@pytest.mark.asyncio
async def test_interface_implementation():
    """测试接口实现完整性"""
    from backend.services.terminal_bridge import TerminalBridge, ITerminalBridge
    
    bridge = TerminalBridge()
    
    # 验证实现了所有接口方法
    assert hasattr(bridge, 'start')
    assert hasattr(bridge, 'stop')
    assert hasattr(bridge, 'send_command')
    assert hasattr(bridge, 'is_alive')
    assert hasattr(bridge, 'set_output_callback')
    
    # 验证是接口的实例
    assert isinstance(bridge, ITerminalBridge)


# ===== 提示符检测测试 =====
@pytest.mark.asyncio
async def test_detect_prompt():
    """测试提示符检测"""
    from backend.services.terminal_bridge import TerminalBridge
    
    bridge = TerminalBridge()
    
    # 测试各种提示符
    test_cases = [
        ("user@host:~$ ", True),
        ("claude-code> ", True),
        ("[user@host]$ ", True),
        ("❯ ", True),
        ("some random text", False),
        ("", False)
    ]
    
    for output, expected in test_cases:
        result = bridge._detect_prompt(output)
        assert result == expected, f"Failed for: {output}"


# ===== 主测试运行器 =====
async def main():
    """运行所有测试"""
    print("🚀 运行 TerminalBridge 完整测试套件")
    print("=" * 80)
    
    tests = [
        # 数据类测试
        test_terminal_state,
        
        # 初始化测试
        test_terminal_bridge_init,
        test_terminal_bridge_configuration,
        
        # 状态检查测试
        test_is_alive,
        test_is_running,
        test_set_output_callback,
        
        # 命令发送测试
        test_send_command_not_started,
        test_send_command_not_ready,
        test_send_command_success,
        test_send_command_error,
        
        # 停止进程测试
        test_stop_not_running,
        
        # 接口实现测试
        test_interface_implementation,
        
        # 提示符检测测试
        test_detect_prompt
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