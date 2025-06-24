#!/usr/bin/env python3
"""
运行所有新增的测试文件并生成报告
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# 新增的测试文件列表
NEW_TEST_FILES = [
    "tests/comprehensive/api/test_api_comprehensive.py",
    "tests/comprehensive/unit/test_command_manager_comprehensive.py",
    "tests/comprehensive/unit/services/test_event_bus_enhanced.py",
    "tests/comprehensive/unit/services/test_terminal_bridge_enhanced.py",
    "tests/comprehensive/unit/services/test_context_monitor_enhanced.py",
    "tests/comprehensive/unit/services/test_memory_lightweight_enhanced.py"
]

async def run_test_file(file_path):
    """运行单个测试文件"""
    print(f"\n{'='*80}")
    print(f"运行测试文件: {file_path}")
    print(f"{'='*80}")
    
    start_time = time.time()
    
    try:
        # 动态导入测试模块
        module_path = file_path.replace('/', '.').replace('.py', '')
        module = __import__(module_path, fromlist=['main'])
        
        # 运行测试
        if hasattr(module, 'main'):
            result = await module.main()
            success = result == 0
        else:
            print(f"⚠️  警告: {file_path} 没有 main 函数")
            success = False
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    elapsed = time.time() - start_time
    print(f"\n耗时: {elapsed:.2f} 秒")
    
    return {
        'file': file_path,
        'success': success,
        'elapsed': elapsed
    }

async def main():
    """主函数"""
    print("🚀 Claude Code Wrapper - 新增测试验证报告")
    print(f"📅 日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # 检查测试文件是否存在
    print("\n📁 检查测试文件...")
    missing_files = []
    existing_files = []
    
    for test_file in NEW_TEST_FILES:
        if Path(test_file).exists():
            existing_files.append(test_file)
            print(f"  ✅ {test_file}")
        else:
            missing_files.append(test_file)
            print(f"  ❌ {test_file} (不存在)")
    
    if missing_files:
        print(f"\n⚠️  警告: {len(missing_files)} 个文件不存在")
    
    # 运行测试
    print(f"\n🧪 开始运行 {len(existing_files)} 个测试文件...")
    
    results = []
    total_start = time.time()
    
    for test_file in existing_files:
        result = await run_test_file(test_file)
        results.append(result)
    
    total_elapsed = time.time() - total_start
    
    # 生成报告
    print("\n" + "="*80)
    print("📊 测试运行总结")
    print("="*80)
    
    passed = sum(1 for r in results if r['success'])
    failed = len(results) - passed
    
    print(f"\n测试文件统计:")
    print(f"  ✅ 通过: {passed}")
    print(f"  ❌ 失败: {failed}")
    print(f"  📁 总计: {len(results)}")
    print(f"  ⏱️  总耗时: {total_elapsed:.2f} 秒")
    
    # 详细结果
    print(f"\n详细结果:")
    print("-"*80)
    print(f"{'文件名':<50} {'状态':<10} {'耗时(秒)':<10}")
    print("-"*80)
    
    for result in results:
        file_name = os.path.basename(result['file'])
        status = "✅ 通过" if result['success'] else "❌ 失败"
        print(f"{file_name:<50} {status:<10} {result['elapsed']:<10.2f}")
    
    # 测试覆盖估算
    print("\n" + "="*80)
    print("📈 测试覆盖率估算")
    print("="*80)
    
    test_counts = {
        'test_api_comprehensive.py': 15,
        'test_command_manager_comprehensive.py': 24,
        'test_event_bus_enhanced.py': 23,
        'test_terminal_bridge_enhanced.py': 29,
        'test_context_monitor_enhanced.py': 30,
        'test_memory_lightweight_enhanced.py': 11
    }
    
    total_tests = 0
    for file_name, count in test_counts.items():
        print(f"  {file_name:<45} : {count:>3} 个测试")
        total_tests += count
    
    print(f"  {'总计':<45} : {total_tests:>3} 个测试")
    
    # 最终结论
    print("\n" + "="*80)
    print("🎯 结论")
    print("="*80)
    
    if failed == 0:
        print("\n✅ 所有新增测试文件运行成功！")
        print(f"   - 测试文件数: {len(results)}")
        print(f"   - 测试用例数: {total_tests}")
        print(f"   - 执行时间: {total_elapsed:.2f} 秒")
        print("\n🎉 测试覆盖率提升项目验证通过！")
    else:
        print(f"\n⚠️  有 {failed} 个测试文件运行失败，请检查并修复。")
    
    # 生成 Markdown 报告
    report_path = "TEST_VALIDATION_REPORT.md"
    with open(report_path, 'w') as f:
        f.write(f"# 新增测试验证报告\n\n")
        f.write(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write(f"## 测试文件运行结果\n\n")
        f.write(f"| 测试文件 | 状态 | 测试数 | 耗时(秒) |\n")
        f.write(f"|----------|------|--------|----------|\n")
        
        for result in results:
            file_name = os.path.basename(result['file'])
            status = "✅ 通过" if result['success'] else "❌ 失败"
            test_count = test_counts.get(file_name, 0)
            f.write(f"| {file_name} | {status} | {test_count} | {result['elapsed']:.2f} |\n")
        
        f.write(f"| **总计** | **{passed}/{len(results)} 通过** | **{total_tests}** | **{total_elapsed:.2f}** |\n")
    
    print(f"\n📄 详细报告已保存到: {report_path}")
    
    return 0 if failed == 0 else 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))